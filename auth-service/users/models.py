from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = (
        ('passenger', 'Passager'),
        ('driver', 'Conducteur'),
        ('both', 'Les deux'),
        ('admin', 'Administrateur'),
    )

    email = models.EmailField(unique=True)
    
    phone_regex = RegexValidator(
        regex=r'^0[567]\d{8}$',
        message="Numéro algérien (ex: 0550123456)"
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=10,
        unique=True,
        null=True,
        blank=True
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='passenger')
    
    is_verified = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.TextField(blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
        # Véhicule
    vehicle_brand = models.CharField(max_length=100, blank=True, default='')
    vehicle_model = models.CharField(max_length=100, blank=True, default='')
    vehicle_year = models.IntegerField(null=True, blank=True)
    vehicle_color = models.CharField(max_length=50, blank=True, default='')
    vehicle_license_plate = models.CharField(max_length=50, blank=True, default='')
    vehicle_seats = models.IntegerField(null=True, blank=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['is_blocked']),
        ]

    def __str__(self):
        return f"{self.email} [{self.role}]"

    def save(self, *args, **kwargs):
        if self.role == 'admin':
            self.is_staff = True
            self.is_superuser = True
        else:
            self.is_staff = False
            self.is_superuser = False
        
        if self.is_blocked and not self.blocked_at:
            self.blocked_at = timezone.now()
        elif not self.is_blocked:
            self.blocked_at = None
        
        super().save(*args, **kwargs)

    def can_publish_trip(self):
        return (self.role in ['driver', 'both', 'admin'] and 
                self.is_verified and not self.is_blocked)
    
    def can_book_trip(self):
        return (self.role in ['passenger', 'both', 'admin'] and 
                not self.is_blocked)
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username


class Profile(models.Model):
    VERIFICATION_STATUS = (
        ('pending', 'En attente'),
        ('verified', 'Vérifié'),
        ('rejected', 'Rejeté'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    city = models.CharField(max_length=100, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    
    driver_license_number = models.CharField(max_length=50, blank=True)
    driver_license_photo = models.ImageField(upload_to='verifications/', null=True, blank=True)
    id_card_photo = models.ImageField(upload_to='verifications/', null=True, blank=True)
    
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='pending')
    verification_rejection_reason = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.IntegerField(null=True, blank=True)
    
    rating_as_driver = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    rating_as_passenger = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    trips_completed = models.PositiveIntegerField(default=0)
    trips_as_driver = models.PositiveIntegerField(default=0)
    trips_as_passenger = models.PositiveIntegerField(default=0)
    car_registration = models.ImageField(upload_to='car_registrations/', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['verification_status'])]

    def __str__(self):
        return f"Profil de {self.user.email}"


class RefreshToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refresh_tokens')
    token = models.CharField(max_length=500, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    revoked = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['user', 'revoked']),
        ]
    
    def is_expired(self):
        return timezone.now() > self.expires_at


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['login_time']),
        ]


# --- SIGNALS ---
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()