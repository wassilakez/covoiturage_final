from django.db import models

class City(models.Model):
    name_ar = models.CharField(max_length=100)
    name_fr = models.CharField(max_length=100)
    wilaya_number = models.IntegerField()
    region = models.CharField(max_length=50)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    
    class Meta:
        managed = False
        db_table = 'trajet_app_city'
    
    def __str__(self):
        return f"{self.name_fr} ({self.wilaya_number})"


class Ride(models.Model):
    driver_id = models.IntegerField()
    vehicle_id = models.IntegerField()
    
    departure_city = models.ForeignKey(
        City, 
        on_delete=models.CASCADE, 
        related_name='departure_rides'
    )
    arrival_city = models.ForeignKey(
        City, 
        on_delete=models.CASCADE, 
        related_name='arrival_rides'
    )
    
    departure_datetime = models.DateTimeField()
    arrival_datetime = models.DateTimeField(null=True, blank=True)
    price_per_seat = models.DecimalField(max_digits=10, decimal_places=2)
    total_seats = models.IntegerField()
    available_seats = models.IntegerField()
    description = models.TextField(blank=True)
    intermediate_stops = models.JSONField(default=list, blank=True)
    gender_preference = models.CharField(max_length=20, default='any')
    smoking_allowed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default='scheduled')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        managed = False
        db_table = 'trajet_app_ride'
    
    def __str__(self):
        return f"{self.departure_city.name_fr} → {self.arrival_city.name_fr}"