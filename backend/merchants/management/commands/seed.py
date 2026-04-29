"""
Management command: python manage.py seed

Seeds 3 merchants with bank accounts and a realistic credit history.
Safe to run multiple times (idempotent via get_or_create).
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from merchants.models import Merchant, BankAccount, LedgerEntry
from payouts.models import Payout
import uuid


SEED_DATA = [
    {
        "name": "Arjun Designs",
        "email": "arjun@arjundesigns.in",
        "bank": {
            "account_holder_name": "Arjun Sharma",
            "account_number": "001234567890",
            "ifsc_code": "HDFC0001234",
        },
        "credits": [
            (2500000, "Initial Project Deposit — Enterprise Design System"),
            (1800000, "Milestone 2: High-fidelity prototypes"),
            (950000, "Advisory retainer — Q1 2024"),
        ],
        "payouts": [
            (1500000, Payout.COMPLETED, "Settled to primary bank"),
            (500000, Payout.PROCESSING, "In transit"),
        ]
    },
    {
        "name": "Priya Writes",
        "email": "priya@priyawrites.com",
        "bank": {
            "account_holder_name": "Priya Nair",
            "account_number": "009876543210",
            "ifsc_code": "ICIC0009876",
        },
        "credits": [
            (1200000, "Technical Documentation — FinCore Module"),
            (750000, "Whitepaper: Future of Decentralized Finance"),
            (500000, "Copywriting retainer — 3 Months"),
        ],
        "payouts": [
            (450000, Payout.COMPLETED, "Monthly withdrawal"),
        ]
    },
    {
        "name": "Dev Studio Co",
        "email": "billing@devstudio.co",
        "bank": {
            "account_holder_name": "Rahul Mehta",
            "account_number": "005544332211",
            "ifsc_code": "SBIN0005544",
        },
        "credits": [
            (5000000, "System Architecture — Neobank Infrastructure"),
            (3200000, "Payment Gateway Integration — Global rollout"),
            (1500000, "Security Audit & Hardening — Enterprise Payouts"),
        ],
        "payouts": [
            (2700000, Payout.COMPLETED, "Corporate dividend"),
            (500000, Payout.FAILED, "Invalid account branch (simulated)"),
        ]
    },
]


class Command(BaseCommand):
    help = "Seed database with test merchants, bank accounts, and credit history"

    @transaction.atomic
    def handle(self, *args, **options):
        for data in SEED_DATA:
            merchant, created = Merchant.objects.get_or_create(
                email=data["email"],
                defaults={"name": data["name"]},
            )
            if created:
                self.stdout.write(f"  Created merchant: {merchant.name}")
            else:
                self.stdout.write(f"  Merchant already exists: {merchant.name}")

            bank_data = data["bank"]
            bank_account, _ = BankAccount.objects.get_or_create(
                merchant=merchant,
                account_number=bank_data["account_number"],
                defaults={
                    "account_holder_name": bank_data["account_holder_name"],
                    "ifsc_code": bank_data["ifsc_code"],
                },
            )

            # Seed credits (idempotent via content check)
            for amount, description in data["credits"]:
                if not LedgerEntry.objects.filter(merchant=merchant, amount_paise=amount, description=description).exists():
                    LedgerEntry.objects.create(
                        merchant=merchant,
                        entry_type=LedgerEntry.CREDIT,
                        amount_paise=amount,
                        description=description,
                    )

            # Seed payouts and their ledger entries
            for amount, status, desc in data["payouts"]:
                # Use a deterministic UUID for idempotency in seed
                seed_key = uuid.uuid5(uuid.NAMESPACE_DNS, f"{merchant.email}-{amount}-{status}-{desc}")
                if not Payout.objects.filter(merchant=merchant, idempotency_key=seed_key).exists():
                    payout = Payout.objects.create(
                        merchant=merchant,
                        bank_account=bank_account,
                        amount_paise=amount,
                        status=status,
                        idempotency_key=seed_key,
                        failure_reason=desc if status == Payout.FAILED else ""
                    )
                    
                    if status == Payout.COMPLETED:
                        LedgerEntry.objects.create(
                            merchant=merchant,
                            entry_type=LedgerEntry.DEBIT,
                            amount_paise=amount,
                            description=desc,
                            payout=payout
                        )
                    self.stdout.write(f"    Created payout: {status} ({amount} paise)")

            balance = merchant.get_balance()
            self.stdout.write(
                self.style.SUCCESS(
                    f"    Account: {merchant.name} | Available: {balance['available_balance_paise'] / 100:.2f} INR"
                )
            )

        # Create Django admin superuser (idempotent)
        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@playto.local", "admin123")
            self.stdout.write(self.style.SUCCESS("  Django admin superuser created: admin / admin123"))

        self.stdout.write(self.style.SUCCESS("Seed complete."))
