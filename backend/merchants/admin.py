from django.contrib import admin
from .models import Merchant, BankAccount, LedgerEntry


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "created_at"]


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ["merchant", "account_holder_name", "account_number", "ifsc_code", "is_active"]
    list_filter = ["is_active", "merchant"]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["merchant", "entry_type", "amount_paise", "description", "created_at"]
    list_filter = ["entry_type", "merchant"]
    ordering = ["-created_at"]
