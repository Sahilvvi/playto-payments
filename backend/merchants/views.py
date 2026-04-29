from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Merchant, LedgerEntry
from .serializers import MerchantSerializer, BalanceSerializer, LedgerEntrySerializer


class MerchantListView(generics.ListAPIView):
    queryset = Merchant.objects.prefetch_related("bank_accounts").order_by("name")
    serializer_class = MerchantSerializer


class MerchantDetailView(generics.RetrieveAPIView):
    queryset = Merchant.objects.prefetch_related("bank_accounts")
    serializer_class = MerchantSerializer
    lookup_field = "id"


@api_view(["GET"])
def merchant_balance(request, id):
    try:
        merchant = Merchant.objects.get(id=id)
    except Merchant.DoesNotExist:
        return Response({"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND)

    balance = merchant.get_balance()
    return Response(BalanceSerializer(balance).data)


@api_view(["GET"])
def merchant_ledger(request, id):
    try:
        merchant = Merchant.objects.get(id=id)
    except Merchant.DoesNotExist:
        return Response({"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND)

    entries = LedgerEntry.objects.filter(merchant=merchant).select_related("payout")
    serializer = LedgerEntrySerializer(entries, many=True)
    return Response(serializer.data)
