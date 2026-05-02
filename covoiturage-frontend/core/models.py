from django.db import models

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('booking_request', 'Demande de réservation'),
        ('booking_confirmed', 'Réservation confirmée'),
        ('booking_cancelled', 'Réservation annulée'),
        ('refund', 'Remboursement'),
        ('penalty', 'Pénalité'),
        ('info', 'Information'),
    ]
    
    user_id = models.IntegerField()
    title = models.CharField(max_length=100, default='Notification')
    message = models.TextField()
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for user {self.user_id}: {self.title}"