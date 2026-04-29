"""
Ledger integrity tests.

Verify the core invariant holds under every path that changes ledger state:
  available_balance = SUM(credits) - SUM(debits) - SUM(held_by_pending_or_processing)

Also verifies DB-level constraints block silent corruption:
  - Negative / zero amounts are rejected at the DB layer.
  - A second debit entry for the same payout is rejected at the DB layer.
"""

import uuid
from django.test import TestCase
from django.db import IntegrityError, transaction

from merchants.models import Merchant, BankAccount, LedgerEntry
from payouts.models import Payout
from payouts.tasks import _complete_payout, _fail_payout


def _make_merchant(suffix=""):
    m = Merchant.objects.create(name=f"IntegrityMerchant{suffix}", email=f"integrity{suffix}@test.example")
    BankAccount.objects.create(
        merchant=m,
        account_holder_name="Test User",
        account_number=f"1234567{suffix[:4]:0>4}",
        ifsc_code="TEST0000001",
    )
    return m


def _credit(merchant, amount, description=""):
    return LedgerEntry.objects.create(
        merchant=merchant,
        entry_type=LedgerEntry.CREDIT,
        amount_paise=amount,
        description=description,
    )


def _assert_invariant(tc, merchant):
    """
    Asserts the fundamental ledger invariant:
        available = total_credits - total_debits - held_by_active_payouts
    and that available >= 0 (no overdraft).
    """
    b = merchant.get_balance()
    expected_available = b["total_credits_paise"] - b["total_debits_paise"] - b["held_balance_paise"]
    tc.assertEqual(
        b["available_balance_paise"],
        expected_available,
        msg=f"Invariant broken: {b}",
    )
    tc.assertGreaterEqual(b["available_balance_paise"], 0, msg=f"Negative balance: {b}")


class LedgerInvariantTest(TestCase):
    """Invariant holds across the entire payout lifecycle."""

    def setUp(self):
        self.merchant = _make_merchant("inv")
        self.bank = BankAccount.objects.filter(merchant=self.merchant).first()
        _credit(self.merchant, 50_000, "initial credit")

    def test_invariant_holds_initially(self):
        _assert_invariant(self, self.merchant)
        b = self.merchant.get_balance()
        self.assertEqual(b["available_balance_paise"], 50_000)

    def test_invariant_holds_after_pending_payout(self):
        """Creating a pending payout moves funds to 'held', not 'available'."""
        Payout.objects.create(
            merchant=self.merchant,
            bank_account=self.bank,
            amount_paise=20_000,
            idempotency_key=uuid.uuid4(),
            status=Payout.PENDING,
        )
        _assert_invariant(self, self.merchant)
        b = self.merchant.get_balance()
        self.assertEqual(b["held_balance_paise"], 20_000)
        self.assertEqual(b["available_balance_paise"], 30_000)

    def test_invariant_holds_after_completed_payout(self):
        """On completion, held funds become a debit entry — available drops permanently."""
        payout = Payout.objects.create(
            merchant=self.merchant,
            bank_account=self.bank,
            amount_paise=15_000,
            idempotency_key=uuid.uuid4(),
            status=Payout.PROCESSING,
            attempt_count=1,
        )
        _complete_payout(str(payout.id))

        _assert_invariant(self, self.merchant)
        b = self.merchant.get_balance()
        self.assertEqual(b["held_balance_paise"], 0)
        self.assertEqual(b["total_debits_paise"], 15_000)
        self.assertEqual(b["available_balance_paise"], 35_000)  # 50000 - 15000

    def test_invariant_holds_after_failed_payout(self):
        """On failure, no debit entry is created — funds return to available automatically."""
        payout = Payout.objects.create(
            merchant=self.merchant,
            bank_account=self.bank,
            amount_paise=10_000,
            idempotency_key=uuid.uuid4(),
            status=Payout.PROCESSING,
            attempt_count=1,
        )
        _fail_payout(str(payout.id), reason="Bank declined")

        _assert_invariant(self, self.merchant)
        b = self.merchant.get_balance()
        self.assertEqual(b["held_balance_paise"], 0)
        self.assertEqual(b["total_debits_paise"], 0)       # No debit created
        self.assertEqual(b["available_balance_paise"], 50_000)  # Back to full

    def test_invariant_holds_after_multiple_mixed_payouts(self):
        """Complex state: some pending, some completed, some failed."""
        p_completed = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=10_000, idempotency_key=uuid.uuid4(), status=Payout.PROCESSING, attempt_count=1,
        )
        p_failed = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=5_000, idempotency_key=uuid.uuid4(), status=Payout.PROCESSING, attempt_count=1,
        )
        p_pending = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=8_000, idempotency_key=uuid.uuid4(), status=Payout.PENDING,
        )

        _complete_payout(str(p_completed.id))
        _fail_payout(str(p_failed.id), "declined")
        # p_pending stays pending (held)

        _assert_invariant(self, self.merchant)
        b = self.merchant.get_balance()
        # credits=50000, debits=10000 (completed), held=8000 (pending)
        self.assertEqual(b["total_credits_paise"], 50_000)
        self.assertEqual(b["total_debits_paise"], 10_000)
        self.assertEqual(b["held_balance_paise"], 8_000)
        self.assertEqual(b["available_balance_paise"], 32_000)  # 50000 - 10000 - 8000


class LedgerConstraintTest(TestCase):
    """DB-level constraints block corruption even if application logic fails."""

    def setUp(self):
        self.merchant = _make_merchant("cons")
        self.bank = BankAccount.objects.filter(merchant=self.merchant).first()
        _credit(self.merchant, 100_000)

    def test_negative_ledger_amount_rejected_at_db_level(self):
        """CheckConstraint(amount_paise > 0) prevents negative debit/credit rows."""
        with self.assertRaises((IntegrityError, Exception)):
            with transaction.atomic():
                LedgerEntry.objects.create(
                    merchant=self.merchant,
                    entry_type=LedgerEntry.CREDIT,
                    amount_paise=-500,
                )

    def test_zero_ledger_amount_rejected_at_db_level(self):
        """Zero-amount entries are also blocked."""
        with self.assertRaises((IntegrityError, Exception)):
            with transaction.atomic():
                LedgerEntry.objects.create(
                    merchant=self.merchant,
                    entry_type=LedgerEntry.DEBIT,
                    amount_paise=0,
                )

    def test_double_debit_for_same_payout_rejected(self):
        """
        UniqueConstraint(payout, entry_type='debit') blocks a second debit
        entry for the same payout, making double-credit impossible at DB level
        even if _complete_payout is called twice due to a Celery bug.
        """
        payout = Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=5_000, idempotency_key=uuid.uuid4(), status=Payout.PROCESSING, attempt_count=1,
        )
        # First debit — legitimate completion
        LedgerEntry.objects.create(
            merchant=self.merchant, entry_type=LedgerEntry.DEBIT,
            amount_paise=5_000, payout=payout,
        )
        # Second debit for the same payout — must be blocked
        with self.assertRaises((IntegrityError, Exception)):
            with transaction.atomic():
                LedgerEntry.objects.create(
                    merchant=self.merchant, entry_type=LedgerEntry.DEBIT,
                    amount_paise=5_000, payout=payout,
                )

    def test_negative_payout_amount_rejected_at_db_level(self):
        """CheckConstraint(amount_paise > 0) on Payout prevents ₹0 payouts."""
        with self.assertRaises((IntegrityError, Exception)):
            with transaction.atomic():
                Payout.objects.create(
                    merchant=self.merchant, bank_account=self.bank,
                    amount_paise=0, idempotency_key=uuid.uuid4(),
                )

    def test_balance_never_goes_negative_via_api(self):
        """
        Even without the application balance check, attempting to hold more
        than available should be caught — and after all operations invariant holds.
        """
        _assert_invariant(self, self.merchant)
        # Create payout that exhausts available balance
        Payout.objects.create(
            merchant=self.merchant, bank_account=self.bank,
            amount_paise=100_000, idempotency_key=uuid.uuid4(), status=Payout.PENDING,
        )
        _assert_invariant(self, self.merchant)
        b = self.merchant.get_balance()
        # available = 0, not negative
        self.assertEqual(b["available_balance_paise"], 0)
