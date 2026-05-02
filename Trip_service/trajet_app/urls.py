 
from django.urls import path
from . import views
from .views import ReserveTripView 
urlpatterns = [
    # Health
    path('health/', views.health_check, name='health'),
    
    # ========== CITIES ==========
    path('cities/', views.CityListView.as_view(), name='city-list'),
    path('cities/<int:pk>/', views.CityDetailView.as_view(), name='city-detail'),
    path('cities/create/', views.CityCreateView.as_view(), name='city-create'),
    path('cities/<int:pk>/update/', views.CityUpdateView.as_view(), name='city-update'),
    path('cities/<int:pk>/delete/', views.CityDeleteView.as_view(), name='city-delete'),
    
    # ========== VEHICLES ==========
    path('vehicles/', views.VehicleListCreateView.as_view(), name='vehicle-list'),
    path('vehicles/create/', views.VehicleCreateView.as_view(), name='vehicle-create'),
    path('vehicles/<int:pk>/', views.VehicleDetailView.as_view(), name='vehicle-detail'),
    path('vehicles/<int:pk>/update/', views.VehicleDetailView.as_view(), name='vehicle-update'),
    path('vehicles/<int:pk>/delete/', views.VehicleDetailView.as_view(), name='vehicle-delete'),
    
    # ========== RIDES ==========
    path('trips/', views.RideListView.as_view(), name='trip-list'),
    path('all-rides/', views.AllRidesView.as_view(), name='all-rides'),
    path('upcoming-rides/', views.UpcomingRidesView.as_view(), name='upcoming-rides'),
    path('past-rides/', views.PastRidesView.as_view(), name='past-rides'),
    path('trips/create/', views.RideCreateView.as_view(), name='trip-create'),
    path('trips/<int:pk>/', views.RideDetailView.as_view(), name='trip-detail'),
    path('trips/<int:pk>/update/', views.RideUpdateView.as_view(), name='trip-update'),
    path('trips/<int:pk>/delete/', views.RideDeleteView.as_view(), name='trip-delete'),
    path('trips/<int:pk>/cancel/', views.CancelRideView.as_view(), name='trip-cancel'),
    path('my-trips/', views.MyRidesView.as_view(), name='my-trips'),
    path('rides/driver/<int:driver_id>/', views.DriverRidesView.as_view(), name='driver-rides'),
    path('trips/<int:pk>/reserve/', views.ReserveTripView.as_view(), name='trip-reserve'),

    # ========== STOPOVERS ==========
    path('rides/<int:ride_id>/stopovers/', views.StopoverListView.as_view(), name='stopover-list'),
    path('rides/<int:ride_id>/stopovers/create/', views.StopoverCreateView.as_view(), name='stopover-create'),
    path('stopovers/<int:pk>/delete/', views.StopoverDeleteView.as_view(), name='stopover-delete'),
    
    # ========== STATISTICS ==========
    path('driver/stats/', views.DriverStatsView.as_view(), name='driver-stats'),
]