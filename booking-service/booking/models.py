from django.db import models

class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('confirmed', 'Confirmé'),
        ('cancelled', 'Annulé'),
        ('completed', 'Terminé'),
        ('refunded', 'Remboursé'),
    ]
    
    PAYMENT_CHOICES = [
        ('cash', 'Espèces'),
        ('card', 'Carte bancaire'),
        ('ccp', 'CCP'),
        ('dahabiya', 'Dahabiya'),
    ]
    
    user_id = models.IntegerField()
    driver_id = models.IntegerField(null=True, blank=True)
    trip_id = models.IntegerField()
    seats_booked = models.IntegerField(default=1)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cash')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ⚠️ AJOUTE CES DEUX CHAMPS ⚠️
    passenger_confirmed = models.BooleanField(default=False)
    driver_confirmed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)
    
    def __str__(self):
        return f'Booking #{self.id} - Trip {self.trip_id}'
class Rating(models.Model):
    booking_id = models.IntegerField(unique=True)
    driver_id = models.IntegerField(db_index=True)
    passenger_name = models.CharField(max_length=255, blank=True)
    passenger_id = models.IntegerField()
    rating = models.IntegerField()  # 1-5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Rating {self.rating}/5 for driver {self.driver_id}"