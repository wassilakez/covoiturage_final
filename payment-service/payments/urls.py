from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('create/', views.create_payment, name='create_payment'),
    path('release/', views.release_payment, name='release_payment'),
    path('refund/<str:transaction_id>/', views.refund_payment, name='refund_payment'),
    path('partial-refund/<str:transaction_id>/', views.partial_refund_payment, name='partial_refund_payment'),
    path('cancel-refund/', views.cancel_booking_refund, name='cancel_booking_refund'),
    path('admin-block/', views.admin_block_payment, name='admin_block_payment'),
    path('transaction/<str:transaction_id>/', views.get_transaction, name='get_transaction'),
    path('wallet/', views.get_wallet, name='get_wallet'),
]