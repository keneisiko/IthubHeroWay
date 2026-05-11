from django.urls import path

from .views import MyPurchaseListView, PurchaseCreateView, ShopItemListView

urlpatterns = [
    path("shop/items/", ShopItemListView.as_view(), name="shop-items"),
    path("shop/purchase/", PurchaseCreateView.as_view(), name="shop-purchase"),
    path("shop/my-purchases/", MyPurchaseListView.as_view(), name="shop-my-purchases"),
]

