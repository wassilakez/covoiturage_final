from django.contrib import admin
from .models import City, Vehicle, Ride, Stopover

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_fr', 'wilaya_number', 'region')
    search_fields = ('name_ar', 'name_fr', 'wilaya_number')
    list_filter = ('region', 'is_active')

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('brand', 'model', 'license_plate', 'seats', 'is_verified')
    search_fields = ('brand', 'model', 'license_plate')
    list_filter = ('vehicle_type', 'is_verified')

@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ('id', 'departure_city', 'arrival_city', 'departure_datetime', 'price_per_seat', 'available_seats', 'status')
    search_fields = ('departure_city__name_fr', 'arrival_city__name_fr')
    list_filter = ('status', 'departure_datetime')
    date_hierarchy = 'departure_datetime'

@admin.register(Stopover)
class StopoverAdmin(admin.ModelAdmin):
    list_display = ('ride', 'city', 'order')
    list_filter = ('city',)