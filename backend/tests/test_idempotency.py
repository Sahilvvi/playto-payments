"""
Idempotency tests: same Idempotency-Key returns identical response, no duplicate payout.
"""

import uuid
from datetime import timedelta

from django.test import TestCase, Client
from django.utils import timezone
from merchants.models import Merchant, BankAccount, LedgerEntry
from payouts.models import Payout


class IdempotencyTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Idempotency Merchant",
            email="idempotency@test.example",
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_holder_name="Test User",
            account_number="1111111111",
            ifsc_code="IDEM0000001",
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type=LedgerEntry.CREDIT,
            amount_paise=50_000,
            description="Credit for idempotency tests",
        )
        self.client = Client()
        self.key = str(uuid.uuid4())
        self.headers = {
            "HTTP_IDEMPOTENCY_KEY": self.key,
            "HTTP_X_MERCHANT_ID": str(self.merchant.id),
        }

    def _post_payout(self, amount=10_000):
        return self.client.post(
            "/api/v1/payouts/",
            data={"amount_paise": amount, "bank_account_id": str(self.bank_account.id)},
            content_type="application/json",
            **self.headers,
        )

    def test_second_call_returns_same_response(self):
        r1 = self._post_payout()
        r2 = self._post_payout()

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 200)  # idempotency hit

        data1 = r1.json()
        data2 = r2.json()

        # Same payout id, same amount, same idempotency key
        self.assertEqual(data1["id"], data2["id"])
        self.assertEqual(data1["amount_paise"], data2["amount_paise"])
        self.assertEqual(data1["idempotency_key"], data2["idempotency_key"])

    def test_no_duplicate_payout_created(self):
        self._post_payout()
        self._post_payout()
        self._post_payout()

        count = Payout.objects.filter(
            merchant=self.merchant, idempotency_key=self.key
        ).count()
        self.assertEqual(count, 1, msg="Duplicate payouts were created despite same idempotency key")

    def test_different_keys_create_separate_payouts(self):
        keys = [str(uuid.uuid4()) for _ in range(3)]
        for key in keys:
            resp = self.client.post(
                "/api/v1/payouts/",
                data={"amount_paise": 5_000, "bank_account_id": str(self.bank_account.id)},
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=key,
                HTTP_X_MERCHANT_ID=str(self.merchant.id),
            )
            self.assertEqual(resp.status_code, 201)

        self.assertEqual(Payout.objects.filter(merchant=self.merchant).count(), 3)

    def test_expired_key_returns_409(self):
        r1 = self._post_payout()
        self.assertEqual(r1.status_code, 201)

        # Manually expire the key
        Payout.objects.filter(merchant=self.merchant, idempotency_key=self.key).update(
            idempotency_key_created_at=timezone.now() - timedelta(hours=25)
        )

        r2 = self._post_payout()
        self.assertEqual(r2.status_code, 409)

    def test_missing_idempotency_key_returns_400(self):
        resp = self.client.post(
            "/api/v1/payouts/",
            data={"amount_paise": 1_000, "bank_account_id": str(self.bank_account.id)},
            content_type="application/json",
            HTTP_X_MERCHANT_ID=str(self.merchant.id),
        )
        self.assertEqual(resp.status_code, 400)

    def test_keys_are_scoped_per_merchant(self):
        """The same UUID key used by two different merchants creates two separate payouts."""
        merchant2 = Merchant.objects.create(name="Other Merchant", email="other@test.example")
        BankAccount.objects.create(
            merchant=merchant2,
            account_holder_name="Other User",
            account_number="2222222222",
            ifsc_code="OTHR0000002",
        )
        LedgerEntry.objects.create(
            merchant=merchant2,
            entry_type=LedgerEntry.CREDIT,
            amount_paise=20_000,
        )
        bank2 = BankAccount.objects.filter(merchant=merchant2).first()

        shared_key = str(uuid.uuid4())

        r1 = self.client.post(
            "/api/v1/payouts/",
            data={"amount_paise": 5_000, "bank_account_id": str(self.bank_account.id)},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=shared_key,
            HTTP_X_MERCHANT_ID=str(self.merchant.id),
        )
        r2 = self.client.post(
            "/api/v1/payouts/",
            data={"amount_paise": 5_000, "bank_account_id": str(bank2.id)},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=shared_key,
            HTTP_X_MERCHANT_ID=str(merchant2.id),
        )

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        # Two separate payouts — different merchants, same key string
        self.assertNotEqual(r1.json()["id"], r2.json()["id"])
