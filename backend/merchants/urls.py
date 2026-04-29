from django.urls import path
from . import views

urlpatterns = [
    path("merchants/", views.MerchantListView.as_view(), name="merchant-list"),
    path("merchants/<uuid:id>/", views.MerchantDetailView.as_view(), name="merchant-detail"),
    path("merchants/<uuid:id>/balance/", views.merchant_balance, name="merchant-balance"),
    path("merchants/<uuid:id>/ledger/", views.merchant_ledger, name="merchant-ledger"),
]
