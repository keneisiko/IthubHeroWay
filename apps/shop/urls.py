from django.urls import path

from .views import MyPurchaseListView, PurchaseApplyView, PurchaseCreateView, ShopItemListView

urlpatterns = [
    path("shop/items/", ShopItemListView.as_view(), name="shop-items"),
    path("shop/purchase/", PurchaseCreateView.as_view(), name="shop-purchase"),
    path("shop/my-purchases/", MyPurchaseListView.as_view(), name="shop-my-purchases"),
    path(
        "shop/purchases/<int:purchase_id>/apply/",
        PurchaseApplyView.as_view(),
        name="shop-purchase-apply",
    ),
]

