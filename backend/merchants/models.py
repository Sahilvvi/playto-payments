import uuid
from django.db import models
from django.db.models import Sum, Q, Value, BigIntegerField
from django.db.models.functions import Coalesce


# Maximum single payout: ₹10 lakh = 1,00,00,000 paise
MAX_PAYOUT_PAISE = 10_000_000


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_balance(self):
        """
        Compute balance breakdown entirely in the database.

        available = total_credits - total_debits - held_by_active_payouts
        held      = sum of pending/processing payouts (funds reserved but not settled)
        total     = available + held  (i.e. total_credits - total_debits)

        Debits are only created when a payout COMPLETES, so a failed payout
        automatically releases its hold without a compensating entry.
        """
        from payouts.models import Payout

        ledger = LedgerEntry.objects.filter(merchant=self).aggregate(
            credits=Coalesce(
                Sum("amount_paise", filter=Q(entry_type=LedgerEntry.CREDIT)),
                Value(0),
                output_field=BigIntegerField(),
            ),
            debits=Coalesce(
                Sum("amount_paise", filter=Q(entry_type=LedgerEntry.DEBIT)),
                Value(0),
                output_field=BigIntegerField(),
            ),
        )

        held = Payout.objects.filter(
            merchant=self,
            status__in=[Payout.PENDING, Payout.PROCESSING],
        ).aggregate(
            total=Coalesce(Sum("amount_paise"), Value(0), output_field=BigIntegerField())
        )["total"]

        total = ledger["credits"] - ledger["debits"]
        available = total - held

        return {
            "total_credits_paise": ledger["credits"],
            "total_debits_paise": ledger["debits"],
            "total_balance_paise": total,
            "held_balance_paise": held,
            "available_balance_paise": available,
        }


class BankAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="bank_accounts"
    )
    account_holder_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=20)
    ifsc_code = models.CharField(max_length=11)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_holder_name} ···{self.account_number[-4:]}"


class LedgerEntry(models.Model):
    CREDIT = "credit"
    DEBIT = "debit"
    TYPE_CHOICES = [(CREDIT, "Credit"), (DEBIT, "Debit")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="ledger_entries"
    )
    entry_type = models.CharField(max_length=10, choices=TYPE_CHOICES, db_index=True)
    amount_paise = models.BigIntegerField()
    description = models.TextField(blank=True)
    # Null for credits; points to the completed payout for debits
    payout = models.ForeignKey(
        "payouts.Payout",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Ledger amounts must always be positive. A zero or negative amount
            # in the ledger would silently corrupt balance calculations.
            models.CheckConstraint(
                check=Q(amount_paise__gt=0),
                name="ledgerentry_positive_amount",
            ),
            # Exactly one DEBIT entry per payout — prevents double-debit even if
            # a bug calls _complete_payout twice. Works as a partial unique index:
            # only applies to rows where entry_type='debit', so multiple NULL
            # payout_ids on CREDIT rows are still allowed.
            models.UniqueConstraint(
                fields=["payout"],
                condition=Q(entry_type="debit"),
                name="unique_debit_per_payout",
            ),
        ]

    def __str__(self):
        sign = "+" if self.entry_type == self.CREDIT else "-"
        return f"{sign}{self.amount_paise} paise for {self.merchant.name}"
