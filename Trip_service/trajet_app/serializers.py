 # trajet_app/serializers.py

from rest_framework import serializers
from .models import City, Vehicle, Ride,Stopover
    

class StopoverSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name_fr', read_only=True)
    city_name_ar = serializers.CharField(source='city.name_ar', read_only=True)
    
    class Meta:
        model = Stopover
        fields = ['id', 'ride', 'city', 'city_name', 'city_name_ar', 'order', 'price_to_stop']
        read_only_fields = ['ride']
class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name_ar', 'name_fr', 'wilaya_number', 'region']

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name_ar', 'name_fr', 'wilaya_number', 'region', 'latitude', 'longitude']


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = '__all__'
        read_only_fields = ['owner_id', 'created_at', 'updated_at']


class RideListSerializer(serializers.ModelSerializer):
    departure_city_name = serializers.ReadOnlyField(source='departure_city.name_ar')
    arrival_city_name = serializers.ReadOnlyField(source='arrival_city.name_ar')
    
    class Meta:
        model = Ride
        fields = [
            'id', 'driver_id', 'departure_city', 'departure_city_name',
            'arrival_city', 'arrival_city_name', 'departure_datetime',
            'price_per_seat', 'available_seats', 'status'
        ]


class RideDetailSerializer(serializers.ModelSerializer):
    departure_city_name = serializers.ReadOnlyField(source='departure_city.name_ar')
    arrival_city_name = serializers.ReadOnlyField(source='arrival_city.name_ar')
    vehicle_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Ride
        fields = '__all__'
        read_only_fields = ['driver_id', 'created_at', 'updated_at', 'total_bookings', 'total_revenue']
    
    def get_vehicle_details(self, obj):
        try:
            vehicle = Vehicle.objects.get(id=obj.vehicle_id)
            return VehicleSerializer(vehicle).data
        except Vehicle.DoesNotExist:
            return None


class RideCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = [
            'vehicle_id', 'departure_city', 'arrival_city', 'departure_datetime',
            'price_per_seat', 'total_seats', 'available_seats', 'description',
            'intermediate_stops', 'gender_preference', 'smoking_allowed', 'chat_preference'
        ]
    
    def validate(self, data):
        if data['departure_city'] == data['arrival_city']:
            raise serializers.ValidationError("Departure and arrival cities cannot be the same")
        if data['available_seats'] > data['total_seats']:
            raise serializers.ValidationError("Available seats cannot exceed total seats")
        return data


class SearchSerializer(serializers.Serializer):
    departure_city = serializers.IntegerField(required=False)
    arrival_city = serializers.IntegerField(required=False)
    date = serializers.DateField(required=False)
    passengers = serializers.IntegerField(default=1, min_value=1)
class RideSearchSerializer(serializers.ModelSerializer):
    """خاص بعرض نتائج البحث المختصرة كما في الصورة"""
    departure_city_name = serializers.ReadOnlyField(source='departure_city.name_fr')
    arrival_city_name = serializers.ReadOnlyField(source='arrival_city.name_fr')
    
    class Meta:
        model = Ride
        fields = [
            'id', 'departure_city_name', 'arrival_city_name', 
            'departure_datetime', 'price_per_seat', 'available_seats'
        ]
 
from .models import Stopover

class StopoverSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name_fr', read_only=True)
    
    class Meta:
        model = Stopover
        fields = ['id', 'ride', 'city', 'city_name', 'order', 'price_to_stop']
        read_only_fields = ['ride']