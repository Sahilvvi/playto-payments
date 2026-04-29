"""
Concurrency test: two simultaneous payout requests must not overdraw the balance.

Merchant has 10,000 paise (100 INR).
Two threads each submit a 6,000 paise (60 INR) payout simultaneously.
Exactly one must succeed (201) and the other must be rejected (400).
The ledger invariant must hold after both requests complete.
"""

import threading
import uuid

from django.test import TransactionTestCase, Client
from merchants.models import Merchant, BankAccount, LedgerEntry
from payouts.models import Payout


class ConcurrentPayoutTest(TransactionTestCase):
    """
    TransactionTestCase (not TestCase) is essential here.

    Django's TestCase wraps each test in an outer transaction and rolls it back
    afterwards. That outer transaction prevents SELECT ... FOR UPDATE from
    working correctly across threads because both threads share the same
    savepoint. TransactionTestCase uses real commits, so PostgreSQL row locks
    actually contend and the serialisation logic is exercised for real.
    """

    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Test Merchant",
            email="test@concurrent.example",
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_holder_name="Test User",
            account_number="0000000001",
            ifsc_code="TEST0000001",
        )
        # Seed 100 INR = 10,000 paise
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type=LedgerEntry.CREDIT,
            amount_paise=10_000,
            description="Initial credit for concurrency test",
        )

    def test_two_concurrent_60_rupee_requests_exactly_one_succeeds(self):
        results = []
        lock = threading.Lock()

        def submit_payout():
            client = Client()
            response = client.post(
                "/api/v1/payouts/",
                data={"amount_paise": 6_000, "bank_account_id": str(self.bank_account.id)},
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
                HTTP_X_MERCHANT_ID=str(self.merchant.id),
            )
            with lock:
                results.append(response.status_code)

        t1 = threading.Thread(target=submit_payout)
        t2 = threading.Thread(target=submit_payout)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(sorted(results), [201, 400], msg=f"Got statuses: {sorted(results)}")

        # Only one payout should have been created
        payout_count = Payout.objects.filter(merchant=self.merchant).count()
        self.assertEqual(payout_count, 1)

        # Ledger invariant: available + held == total_credits - total_debits
        balance = self.merchant.get_balance()
        total = balance["total_credits_paise"] - balance["total_debits_paise"]
        self.assertEqual(
            balance["available_balance_paise"] + balance["held_balance_paise"],
            total,
            msg="Balance invariant violated after concurrent requests",
        )

    def test_three_concurrent_requests_respects_balance(self):
        """Three 4,000 paise requests against 10,000 paise: at most 2 succeed."""
        results = []
        lock = threading.Lock()

        def submit():
            client = Client()
            response = client.post(
                "/api/v1/payouts/",
                data={"amount_paise": 4_000, "bank_account_id": str(self.bank_account.id)},
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
                HTTP_X_MERCHANT_ID=str(self.merchant.id),
            )
            with lock:
                results.append(response.status_code)

        threads = [threading.Thread(target=submit) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        success_count = results.count(201)
        self.assertLessEqual(success_count, 2, msg=f"More than 2 payouts succeeded: {results}")

        balance = self.merchant.get_balance()
        self.assertGreaterEqual(balance["available_balance_paise"], 0, msg="Balance went negative")
