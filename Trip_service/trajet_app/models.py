 # trajet_app/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class City(models.Model):
    """Algerian City / Wilaya"""
    name_ar = models.CharField(max_length=100, verbose_name="Name in Arabic")
    name_fr = models.CharField(max_length=100, verbose_name="Name in French")
    wilaya_number = models.IntegerField(unique=True, verbose_name="Wilaya Number")
    region = models.CharField(max_length=50, verbose_name="Region")
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    is_active = models.BooleanField(default=True)
     

    def __str__(self):
        return f"{self.name_ar} ({self.wilaya_number})"
    
    class Meta:
        verbose_name = "City"
        verbose_name_plural = "Cities"
        ordering = ['wilaya_number']


class Vehicle(models.Model):
    """Driver's vehicle"""
    VEHICLE_TYPES = (
        ('car', 'Car'),
        ('van', 'Van'),
        ('bus', 'Bus'),
    )
    
    owner_id = models.IntegerField(verbose_name="Owner ID")
    brand = models.CharField(max_length=50, verbose_name="Brand")
    model = models.CharField(max_length=50, verbose_name="Model")
    year = models.IntegerField(null=True, blank=True, verbose_name="Year")
    color = models.CharField(max_length=30, blank=True, verbose_name="Color")
    license_plate = models.CharField(max_length=20, unique=True, verbose_name="License Plate")
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES, default='car', verbose_name="Vehicle Type")
    seats = models.IntegerField(verbose_name="Number of Seats")
    
    has_air_conditioning = models.BooleanField(default=False, verbose_name="Air Conditioning")
    has_wifi = models.BooleanField(default=False, verbose_name="WiFi")
    has_smoking_allowed = models.BooleanField(default=False, verbose_name="Smoking Allowed")
    has_pets_allowed = models.BooleanField(default=False, verbose_name="Pets Allowed")
    has_luggage_space = models.BooleanField(default=True, verbose_name="Luggage Space")
    
    vehicle_photo = models.ImageField(upload_to='vehicles/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.brand} {self.model} - {self.license_plate}"
    
    class Meta:
        verbose_name = "Vehicle"
        verbose_name_plural = "Vehicles"


class Ride(models.Model):
    """Trip published by a driver"""
    
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    driver_id = models.IntegerField(verbose_name="Driver ID")
    vehicle_id = models.IntegerField(verbose_name="Vehicle ID")
    
    departure_city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='departures', verbose_name="Departure City")
    arrival_city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='arrivals', verbose_name="Arrival City")
    
    departure_datetime = models.DateTimeField(verbose_name="Departure Date and Time")
    arrival_datetime = models.DateTimeField(null=True, blank=True, verbose_name="Arrival Date and Time")
    
    price_per_seat = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Price per Seat")
    total_seats = models.IntegerField(verbose_name="Total Seats")
    available_seats = models.IntegerField(verbose_name="Available Seats")
    
    description = models.TextField(blank=True, verbose_name="Description")
    intermediate_stops = models.JSONField(default=list, blank=True, verbose_name="Intermediate Stops")
    
    gender_preference = models.CharField(max_length=20, default='any', verbose_name="Gender Preference")
    smoking_allowed = models.BooleanField(default=False, verbose_name="Smoking Allowed")
    chat_preference = models.CharField(max_length=20, default='any', verbose_name="Chat Preference")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', verbose_name="Status")
    
    total_bookings = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.departure_city} → {self.arrival_city} - {self.departure_datetime}"
    
    class Meta:
        verbose_name = "Ride"
        verbose_name_plural = "Rides"
        indexes = [
            models.Index(fields=['departure_city', 'arrival_city', 'departure_datetime', 'status']),
            models.Index(fields=['driver_id']),
            models.Index(fields=['status']),
        ]


class Stopover(models.Model):
    """Intermediate stop for a ride"""
    ride = models.ForeignKey(Ride, related_name='stopovers', on_delete=models.CASCADE)
    city = models.ForeignKey(City, on_delete=models.CASCADE, verbose_name="Stop City")
    order = models.PositiveIntegerField(verbose_name="Stop Order")  # 1, 2, 3...
    price_to_stop = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Stopover"
        verbose_name_plural = "Stopovers"
        ordering = ['order']

    def __str__(self):
        return f"{self.city} (Stop {self.order} for Ride {self.ride.id})"