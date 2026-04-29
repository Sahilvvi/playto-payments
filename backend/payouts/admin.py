from django.contrib import admin
from .models import Payout


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = [
        "id", "merchant", "amount_paise", "status",
        "attempt_count", "processing_started_at", "created_at",
    ]
    list_filter = ["status", "merchant"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
