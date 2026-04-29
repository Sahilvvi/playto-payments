"""
Worker safety tests.

Verifies atomicity guarantees when things go wrong:

1. Duplicate worker execution — two Celery workers race to complete the same payout.
   Only one debit entry must be created. The second must be a no-op.

2. Atomicity — _complete_payout is all-or-nothing. If the debit LedgerEntry write
   fails (simulated via monkey-patch), the status update must also be rolled back.

3. Max retries exhaustion — after MAX_ATTEMPTS the payout is moved to FAILED
   and funds are released.

4. Stuck payout recovery — check_and_retry_stuck_payouts correctly identifies
   and re-queues (or fails) stuck payouts based on elapsed time.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone

from merchants.models import Merchant, BankAccount, LedgerEntry
from payouts.models import Payout
from payouts.tasks import (
    _complete_payout,
    _fail_payout,
    process_payout,
    check_and_retry_stuck_payouts,
    MAX_ATTEMPTS,
    RETRY_DELAYS_SECONDS,
)
from payouts.state_machine import InvalidStateTransition


def _make_merchant(suffix=""):
    m = Merchant.objects.create(name=f"WorkerMerchant{suffix}", email=f"worker{suffix}@test.example")
    BankAccount.objects.create(
        merchant=m, account_holder_name="Test",
        account_number=f"WRK{suffix[:6]:0>6}", ifsc_code="WORK0000001",
    )
    return m


class DuplicateWorkerTest(TestCase):
    """Two workers simultaneously call _complete_payout for the same payout."""

    def setUp(self):
        self.merchant = _make_merchant("dup")
        self.bank = BankAccount.objects.filter(merchant=self.merchant).first()
        LedgerEntry.objects.create(
            merchant=self.merchant, entry_type=LedgerEntry.CREDIT, amount_paise=50_000,
        )

    def test_second_complete_is_noop(self):
        """
        The state machine guard (assert_transition_allowed) inside a
        SELECT FOR UPDATE block means the second _complete_payout call sees
        status='completed', raises InvalidStateTransition, and exits without
        creating a duplicate debit entry.
        """
        payout = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=10_000, idempotency_key=uuid.uuid4(),
            status=Payout.PROCESSING, attempt_count=1,
        )
        _complete_payout(str(payout.id))

        # Simulate a second worker calling complete on the same payout
        _complete_payout(str(payout.id))  # must NOT raise, must be a no-op

        # Only one debit entry must exist
        debits = LedgerEntry.objects.filter(
            merchant=self.merchant, entry_type=LedgerEntry.DEBIT, payout=payout,
        )
        self.assertEqual(debits.count(), 1, "Duplicate debit entry created by second worker")

        # Invariant still holds
        b = self.merchant.get_balance()
        self.assertEqual(b["total_debits_paise"], 10_000)
        self.assertEqual(b["available_balance_paise"], 40_000)

    def test_complete_after_fail_is_noop(self):
        """A payout that has already failed cannot be completed."""
        payout = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=5_000, idempotency_key=uuid.uuid4(),
            status=Payout.PROCESSING, attempt_count=1,
        )
        _fail_payout(str(payout.id), "Bank declined")

        # Attempting to complete a failed payout must be a no-op
        _complete_payout(str(payout.id))  # must NOT raise

        # No debit entry should exist
        self.assertEqual(
            LedgerEntry.objects.filter(entry_type=LedgerEntry.DEBIT, payout=payout).count(), 0
        )
        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.FAILED)

    def test_fail_after_complete_is_noop(self):
        """A completed payout cannot be retroactively failed (no double-credit)."""
        payout = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=5_000, idempotency_key=uuid.uuid4(),
            status=Payout.PROCESSING, attempt_count=1,
        )
        _complete_payout(str(payout.id))
        _fail_payout(str(payout.id), "Late failure signal")  # must be a no-op

        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.COMPLETED)
        # Debit entry still exists (wasn't rolled back)
        self.assertEqual(
            LedgerEntry.objects.filter(entry_type=LedgerEntry.DEBIT, payout=payout).count(), 1
        )


class AtomicityTest(TestCase):
    """
    _complete_payout must be all-or-nothing.
    If the LedgerEntry write fails, the status update must also roll back.
    """

    def setUp(self):
        self.merchant = _make_merchant("atom")
        self.bank = BankAccount.objects.filter(merchant=self.merchant).first()
        LedgerEntry.objects.create(
            merchant=self.merchant, entry_type=LedgerEntry.CREDIT, amount_paise=30_000,
        )

    def test_complete_payout_rolls_back_if_ledger_write_fails(self):
        """
        Simulate a crash inside the transaction after the status update but
        before the ledger write (by forcing LedgerEntry.objects.create to raise).
        The payout must remain in PROCESSING, not COMPLETED.
        """
        payout = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=10_000, idempotency_key=uuid.uuid4(),
            status=Payout.PROCESSING, attempt_count=1,
        )

        original_create = LedgerEntry.objects.create

        def boom(*args, **kwargs):
            raise RuntimeError("Simulated DB crash during ledger write")

        with patch.object(LedgerEntry.objects, "create", side_effect=boom):
            with self.assertRaises(RuntimeError):
                _complete_payout(str(payout.id))

        # Both the status update AND ledger entry must have been rolled back
        payout.refresh_from_db()
        self.assertEqual(
            payout.status, Payout.PROCESSING,
            "Status updated to COMPLETED despite ledger write failure — atomicity broken",
        )
        self.assertEqual(
            LedgerEntry.objects.filter(entry_type=LedgerEntry.DEBIT, payout=payout).count(), 0,
            "Debit entry created despite transaction rollback",
        )


class MaxRetriesTest(TestCase):
    """Payout exhausts all retries and is moved to FAILED."""

    def setUp(self):
        self.merchant = _make_merchant("retry")
        self.bank = BankAccount.objects.filter(merchant=self.merchant).first()
        LedgerEntry.objects.create(
            merchant=self.merchant, entry_type=LedgerEntry.CREDIT, amount_paise=20_000,
        )

    def test_payout_fails_after_max_attempts(self):
        """
        A payout that has already used MAX_ATTEMPTS is failed immediately
        by process_payout without incrementing the counter further.
        """
        payout = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=5_000, idempotency_key=uuid.uuid4(),
            status=Payout.PROCESSING, attempt_count=MAX_ATTEMPTS,
        )
        process_payout(str(payout.id))

        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.FAILED)
        self.assertEqual(payout.attempt_count, MAX_ATTEMPTS)  # count not incremented

        # Funds released — no debit entry
        self.assertEqual(
            LedgerEntry.objects.filter(entry_type=LedgerEntry.DEBIT, payout=payout).count(), 0
        )
        b = self.merchant.get_balance()
        self.assertEqual(b["held_balance_paise"], 0)
        self.assertEqual(b["available_balance_paise"], 20_000)  # funds back


class StuckPayoutRecoveryTest(TestCase):
    """check_and_retry_stuck_payouts correctly handles stuck payouts."""

    def setUp(self):
        self.merchant = _make_merchant("stuck")
        self.bank = BankAccount.objects.filter(merchant=self.merchant).first()
        LedgerEntry.objects.create(
            merchant=self.merchant, entry_type=LedgerEntry.CREDIT, amount_paise=50_000,
        )

    def test_stuck_payout_under_threshold_not_retried(self):
        """A payout stuck for less than the retry threshold is left alone."""
        payout = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=5_000, idempotency_key=uuid.uuid4(),
            status=Payout.PROCESSING, attempt_count=1,
            processing_started_at=timezone.now() - timedelta(seconds=10),  # only 10s ago
        )
        with patch("payouts.tasks.process_payout.delay") as mock_delay:
            check_and_retry_stuck_payouts()
            mock_delay.assert_not_called()

        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.PROCESSING)

    def test_stuck_payout_over_threshold_requeued(self):
        """A payout stuck for longer than threshold is re-queued."""
        payout = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=5_000, idempotency_key=uuid.uuid4(),
            status=Payout.PROCESSING, attempt_count=1,
            processing_started_at=timezone.now() - timedelta(seconds=RETRY_DELAYS_SECONDS[0] + 5),
        )
        with patch("payouts.tasks.process_payout.delay") as mock_delay:
            check_and_retry_stuck_payouts()
            mock_delay.assert_called_once_with(str(payout.id))

    def test_stuck_payout_exceeding_max_attempts_failed(self):
        """A payout that has exhausted all attempts is moved to FAILED."""
        payout = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=5_000, idempotency_key=uuid.uuid4(),
            status=Payout.PROCESSING, attempt_count=MAX_ATTEMPTS,
            processing_started_at=timezone.now() - timedelta(seconds=RETRY_DELAYS_SECONDS[-1] + 5),
        )
        check_and_retry_stuck_payouts()

        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.FAILED)
        self.assertIn("Max retries", payout.failure_reason)

        # Funds released
        b = self.merchant.get_balance()
        self.assertEqual(b["held_balance_paise"], 0)
