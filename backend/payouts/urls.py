from django.urls import path
from . import views

urlpatterns = [
    path("payouts/", views.create_payout, name="payout-create"),
    path("payouts/list/", views.list_payouts, name="payout-list"),
    path("payouts/<uuid:payout_id>/", views.get_payout, name="payout-detail"),
]
