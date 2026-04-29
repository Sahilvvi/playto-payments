"""
Payout processing tasks.

Lifecycle
---------
pending  --[process_payout]--> processing --[70%]--> completed
                                           --[20%]--> failed
                                           --[10%]--> (hung, stays in processing)

Hung payouts are detected by check_and_retry_stuck_payouts (runs every 10s).
Payouts stuck in processing for > 30s are retried up to 3 times total, then
moved to failed with funds released.

Atomicity guarantees
--------------------
- complete_payout: status -> completed + debit LedgerEntry in ONE transaction.
- fail_payout:     status -> failed in ONE transaction (no ledger entry needed;
                   the held-balance query excludes failed payouts automatically).
Both use SELECT ... FOR UPDATE on the payout row so concurrent retries are safe.
"""

import logging
import random
import time
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from merchants.models import LedgerEntry
from .models import Payout
from .state_machine import assert_transition_allowed, InvalidStateTransition

logger = logging.getLogger("payouts")

MAX_ATTEMPTS = 3
# Exponential backoff: attempt 1 retries after 30s, attempt 2 after 60s, attempt 3 after 120s
RETRY_DELAYS_SECONDS = [30, 60, 120]


# ---------------------------------------------------------------------------
# Internal helpers (not Celery tasks)
# ---------------------------------------------------------------------------

def _complete_payout(payout_id: str) -> None:
    """
    Atomically: transition payout to completed + create the debit ledger entry.

    Both operations happen in a single transaction protected by SELECT FOR UPDATE
    on the payout row. If two workers race to complete the same payout, the
    second one will find status != PROCESSING and return without a double-credit.
    """
    with transaction.atomic():
        try:
            payout = Payout.objects.select_for_update().get(id=payout_id)
        except Payout.DoesNotExist:
            logger.warning("complete_payout: payout %s not found", payout_id)
            return

        try:
            assert_transition_allowed(payout.status, Payout.COMPLETED)
        except InvalidStateTransition:
            logger.warning(
                "complete_payout: invalid transition for payout %s (%s -> completed)",
                payout_id, payout.status,
            )
            return

        payout.status = Payout.COMPLETED
        payout.save(update_fields=["status", "updated_at"])

        # Create the debit entry atomically with the state transition.
        # This is the ONLY place a debit entry is ever created for a payout.
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            entry_type=LedgerEntry.DEBIT,
            amount_paise=payout.amount_paise,
            description=f"Payout settled to bank account ···{payout.bank_account.account_number[-4:]}",
            payout=payout,
        )

    logger.info("Payout %s completed, debit entry created.", payout_id)


def _fail_payout(payout_id: str, reason: str = "") -> None:
    """
    Atomically: transition payout to failed.

    No ledger entry is created. The held-balance query filters on
    status IN ('pending', 'processing'), so a failed payout is
    automatically excluded and its amount flows back to available balance.
    """
    with transaction.atomic():
        try:
            payout = Payout.objects.select_for_update().get(id=payout_id)
        except Payout.DoesNotExist:
            logger.warning("fail_payout: payout %s not found", payout_id)
            return

        try:
            assert_transition_allowed(payout.status, Payout.FAILED)
        except InvalidStateTransition:
            logger.warning(
                "fail_payout: invalid transition for payout %s (%s -> failed)",
                payout_id, payout.status,
            )
            return

        payout.status = Payout.FAILED
        payout.failure_reason = reason
        payout.save(update_fields=["status", "failure_reason", "updated_at"])

    logger.info("Payout %s failed: %s. Funds released.", payout_id, reason)


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@shared_task(name="payouts.tasks.process_payout")
def process_payout(payout_id: str) -> None:
    """
    Pick up a single payout and drive it through the bank-simulation lifecycle.

    Can be called on PENDING or (by the retry path) already-PROCESSING payouts.
    """
    with transaction.atomic():
        try:
            payout = Payout.objects.select_for_update().get(id=payout_id)
        except Payout.DoesNotExist:
            logger.warning("process_payout: payout %s not found", payout_id)
            return

        if payout.status not in (Payout.PENDING, Payout.PROCESSING):
            logger.info("process_payout: payout %s already terminal (%s)", payout_id, payout.status)
            return

        if payout.attempt_count >= MAX_ATTEMPTS:
            # Should be caught by the stuck checker, but guard here too.
            payout.status = Payout.FAILED
            payout.failure_reason = "Max retries exceeded"
            payout.save(update_fields=["status", "failure_reason", "updated_at"])
            logger.info("Payout %s exceeded max attempts, marked failed.", payout_id)
            return

        # Transition to processing and record attempt.
        payout.status = Payout.PROCESSING
        payout.processing_started_at = timezone.now()
        payout.attempt_count += 1
        payout.save(update_fields=["status", "processing_started_at", "attempt_count", "updated_at"])

    logger.info(
        "Payout %s -> processing (attempt %d/%d)", payout_id, payout.attempt_count, MAX_ATTEMPTS
    )

    # --- SIMULATE BANK SETTLEMENT ---
    # This intentionally runs OUTSIDE the transaction so we don't hold the row
    # lock while waiting for a fake "network" call.
    time.sleep(random.uniform(0.3, 1.5))

    roll = random.random()
    if roll < 0.70:
        _complete_payout(payout_id)
    elif roll < 0.90:
        _fail_payout(payout_id, "Bank declined the transfer")
    else:
        # 10 %: intentional hang — leave payout in PROCESSING.
        # check_and_retry_stuck_payouts will detect it after STUCK_THRESHOLD_SECONDS.
        logger.info(
            "Payout %s simulating hung bank response (will be retried by stuck-checker).",
            payout_id,
        )


@shared_task(name="payouts.tasks.pickup_pending_payouts")
def pickup_pending_payouts() -> None:
    """Fallback sweep: dispatch any pending payouts not yet picked up."""
    pending_ids = list(
        Payout.objects.filter(status=Payout.PENDING).values_list("id", flat=True)
    )
    for pid in pending_ids:
        process_payout.delay(str(pid))
    if pending_ids:
        logger.info("pickup_pending_payouts: dispatched %d task(s)", len(pending_ids))


@shared_task(name="payouts.tasks.check_and_retry_stuck_payouts")
def check_and_retry_stuck_payouts() -> None:
    """
    Find payouts stuck in PROCESSING and retry with exponential backoff.

    Backoff schedule (based on attempt_count when processing started):
      attempt 1 -> retry after 30s
      attempt 2 -> retry after 60s
      attempt 3 -> retry after 120s, then fail

    We use the most conservative threshold (30s) to scan, then filter
    per-payout based on its own attempt count.
    """
    now = timezone.now()
    min_threshold = now - timedelta(seconds=RETRY_DELAYS_SECONDS[0])

    stuck = list(
        Payout.objects.filter(
            status=Payout.PROCESSING,
            processing_started_at__lt=min_threshold,
        ).values_list("id", "attempt_count", "processing_started_at")
    )

    for payout_id, attempt_count, started_at in stuck:
        # Determine required delay for THIS attempt (exponential backoff)
        delay_idx = min(attempt_count - 1, len(RETRY_DELAYS_SECONDS) - 1)
        required_delay = RETRY_DELAYS_SECONDS[delay_idx]
        elapsed = (now - started_at).total_seconds()

        if elapsed < required_delay:
            continue  # Not yet time to retry this attempt

        if attempt_count < MAX_ATTEMPTS:
            logger.info(
                "Stuck payout %s (attempt %d, elapsed %.0fs >= %ds), re-queuing.",
                payout_id, attempt_count, elapsed, required_delay,
            )
            process_payout.delay(str(payout_id))
        else:
            logger.warning(
                "Stuck payout %s exceeded max attempts (%d), failing.",
                payout_id, MAX_ATTEMPTS,
            )
            _fail_payout(str(payout_id), "Max retries exceeded (stuck in processing)")
