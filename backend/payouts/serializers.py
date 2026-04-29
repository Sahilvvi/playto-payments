from rest_framework import serializers
from .models import Payout

# Max single payout: ₹10 lakh (1,00,00,000 paise).
# Prevents accidental 9-digit amounts from draining a merchant's entire wallet
# in one request. Adjust per product limits.
MAX_PAYOUT_PAISE = 10_000_000


class PayoutSerializer(serializers.ModelSerializer):
    merchant_id = serializers.UUIDField(source="merchant.id", read_only=True)
    bank_account_id = serializers.UUIDField(source="bank_account.id", read_only=True)

    class Meta:
        model = Payout
        fields = [
            "id",
            "merchant_id",
            "bank_account_id",
            "amount_paise",
            "status",
            "idempotency_key",
            "attempt_count",
            "processing_started_at",
            "failure_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CreatePayoutSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1, max_value=MAX_PAYOUT_PAISE)
    bank_account_id = serializers.UUIDField()

    def validate_amount_paise(self, value):
        if value <= 0:
            raise serializers.ValidationError("amount_paise must be positive.")
        if value > MAX_PAYOUT_PAISE:
            raise serializers.ValidationError(
                f"amount_paise cannot exceed {MAX_PAYOUT_PAISE} "
                f"(₹{MAX_PAYOUT_PAISE / 100:,.0f}). Contact support for larger payouts."
            )
        return value
