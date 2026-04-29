import logging
import time
import uuid

from django.db import transaction, OperationalError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from merchants.models import Merchant, BankAccount
from .models import Payout
from .serializers import CreatePayoutSerializer, PayoutSerializer
from .tasks import process_payout

logger = logging.getLogger("payouts")


def _get_merchant(request):
    merchant_id = request.headers.get("X-Merchant-ID")
    if not merchant_id:
        return None, Response(
            {"error": "X-Merchant-ID header is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        return Merchant.objects.get(id=merchant_id), None
    except (Merchant.DoesNotExist, ValueError):
        return None, Response(
            {"error": "Merchant not found"},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["POST"])
def create_payout(request):
    """
    POST /api/v1/payouts/

    Required headers:
        Idempotency-Key: <uuid>   — merchant-supplied, scoped per merchant
        X-Merchant-ID:  <uuid>   — identifies the requesting merchant

    Concurrency safety:
        We SELECT ... FOR UPDATE on the Merchant row inside a transaction.
        This serialises all payout creation for a given merchant so the
        check-then-deduct is atomic at the database level — not Python level.

    Idempotency:
        We look for a Payout with the same (merchant, idempotency_key) inside
        the same locked transaction. If found and the key is not expired we
        return the existing payout unchanged (HTTP 200). The second caller
        blocks on the merchant lock until the first caller's transaction
        commits, then finds the already-created row.
    """
    merchant, err = _get_merchant(request)
    if err:
        return err

    raw_key = request.headers.get("Idempotency-Key")
    if not raw_key:
        return Response(
            {"error": "Idempotency-Key header is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        idempotency_key = uuid.UUID(raw_key)
    except ValueError:
        return Response(
            {"error": "Idempotency-Key must be a valid UUID"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = CreatePayoutSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    amount_paise = serializer.validated_data["amount_paise"]
    bank_account_id = serializer.validated_data["bank_account_id"]

    # Retry up to 3 times on SQLite table-lock contention (PostgreSQL uses
    # row-level locking so this path is never hit in production).
    for _attempt in range(3):
        try:
            with transaction.atomic():
                # --- THE LOCK ---
                # SELECT ... FOR UPDATE on the merchant row serialises all payout
                # creation for this merchant. Two simultaneous 60-rupee requests on
                # a 100-rupee balance: one acquires the lock, deducts, commits; the
                # other then acquires it, sees 40 available, and is rejected cleanly.
                merchant = Merchant.objects.select_for_update().get(id=merchant.id)

                # --- IDEMPOTENCY CHECK (inside the lock) ---
                existing = (
                    Payout.objects.filter(merchant=merchant, idempotency_key=idempotency_key)
                    .first()
                )
                if existing:
                    if existing.idempotency_key_expired:
                        return Response(
                            {"error": "Idempotency key has expired (>24 hours). Use a new key."},
                            status=status.HTTP_409_CONFLICT,
                        )
                    logger.info("Idempotency hit: payout %s for key %s", existing.id, idempotency_key)
                    return Response(PayoutSerializer(existing).data, status=status.HTTP_200_OK)

                # --- BANK ACCOUNT VALIDATION ---
                try:
                    bank_account = BankAccount.objects.get(
                        id=bank_account_id, merchant=merchant, is_active=True
                    )
                except BankAccount.DoesNotExist:
                    return Response(
                        {"error": "Bank account not found or inactive"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # --- BALANCE CHECK (DB-level aggregation, same transaction) ---
                balance = merchant.get_balance()
                available = balance["available_balance_paise"]

                if available < amount_paise:
                    return Response(
                        {
                            "error": "Insufficient funds",
                            "available_paise": available,
                            "requested_paise": amount_paise,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # --- CREATE PAYOUT (holds funds) ---
                payout = Payout.objects.create(
                    merchant=merchant,
                    bank_account=bank_account,
                    amount_paise=amount_paise,
                    idempotency_key=idempotency_key,
                    status=Payout.PENDING,
                )
            break  # success — exit retry loop

        except OperationalError as exc:
            if "locked" in str(exc).lower() and _attempt < 2:
                time.sleep(0.05 * (2 ** _attempt))  # 50ms, 100ms
                continue
            raise

    logger.info("Created payout %s for %s paise", payout.id, amount_paise)

    # Dispatch async worker outside the transaction to avoid lock contention.
    process_payout.delay(str(payout.id))

    return Response(PayoutSerializer(payout).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def list_payouts(request):
    merchant, err = _get_merchant(request)
    if err:
        return err

    payouts = Payout.objects.filter(merchant=merchant).select_related(
        "bank_account"
    )
    return Response(PayoutSerializer(payouts, many=True).data)


@api_view(["GET"])
def get_payout(request, payout_id):
    merchant, err = _get_merchant(request)
    if err:
        return err

    try:
        payout = Payout.objects.get(id=payout_id, merchant=merchant)
    except Payout.DoesNotExist:
        return Response({"error": "Payout not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response(PayoutSerializer(payout).data)
