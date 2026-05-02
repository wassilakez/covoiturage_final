from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BookingViewSet, get_driver_ratings, get_all_ratings, create_rating
from .sync_endpoint import sync_user

router = DefaultRouter()
router.register(r'bookings', BookingViewSet, basename='booking')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/users/sync/', sync_user, name='sync_user'),
    path('ratings/driver/<int:driver_id>/', get_driver_ratings, name='driver_ratings'),
    path('ratings/', get_all_ratings, name='all_ratings'),
    path('ratings/create/', create_rating, name='create_rating'),
]