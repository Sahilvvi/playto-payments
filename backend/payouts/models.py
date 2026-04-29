import uuid
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Payout(models.Model):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (PROCESSING, "Processing"),
        (COMPLETED, "Completed"),
        (FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="payouts"
    )
    bank_account = models.ForeignKey(
        "merchants.BankAccount", on_delete=models.PROTECT, related_name="payouts"
    )
    amount_paise = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING, db_index=True)

    # Merchant-supplied idempotency key, scoped per merchant.
    # unique_together ensures no duplicate payouts for the same (merchant, key).
    idempotency_key = models.UUIDField(db_index=True)
    idempotency_key_created_at = models.DateTimeField(default=timezone.now)

    attempt_count = models.PositiveSmallIntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Idempotency keys are scoped per merchant (not globally unique).
        unique_together = [("merchant", "idempotency_key")]
        ordering = ["-created_at"]
        indexes = [
            # Used by check_and_retry_stuck_payouts to find stuck PROCESSING rows.
            models.Index(fields=["status", "processing_started_at"]),
        ]
        constraints = [
            # Payout amounts must always be positive paise. Enforced at DB level
            # so a serializer bug or direct DB write can never create a ₹0 payout.
            models.CheckConstraint(
                check=Q(amount_paise__gt=0),
                name="payout_positive_amount",
            ),
        ]

    def __str__(self):
        return f"Payout {self.id} [{self.status}] {self.amount_paise} paise"

    @property
    def is_terminal(self) -> bool:
        return self.status in (self.COMPLETED, self.FAILED)

    @property
    def idempotency_key_expired(self) -> bool:
        from datetime import timedelta
        return (timezone.now() - self.idempotency_key_created_at) > timedelta(hours=24)
