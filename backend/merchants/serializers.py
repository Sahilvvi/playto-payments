from rest_framework import serializers
from .models import Merchant, BankAccount, LedgerEntry


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ["id", "account_holder_name", "account_number", "ifsc_code", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class MerchantSerializer(serializers.ModelSerializer):
    bank_accounts = BankAccountSerializer(many=True, read_only=True)

    class Meta:
        model = Merchant
        fields = ["id", "name", "email", "created_at", "bank_accounts"]
        read_only_fields = ["id", "created_at"]


class BalanceSerializer(serializers.Serializer):
    total_credits_paise = serializers.IntegerField()
    total_debits_paise = serializers.IntegerField()
    total_balance_paise = serializers.IntegerField()
    held_balance_paise = serializers.IntegerField()
    available_balance_paise = serializers.IntegerField()


class LedgerEntrySerializer(serializers.ModelSerializer):
    payout_id = serializers.UUIDField(source="payout.id", read_only=True, allow_null=True)

    class Meta:
        model = LedgerEntry
        fields = ["id", "entry_type", "amount_paise", "description", "payout_id", "created_at"]
        read_only_fields = fields
