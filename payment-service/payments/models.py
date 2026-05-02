# payments/models.py

from django.db import models
import uuid
from decimal import Decimal

class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'En attente'
    PROCESSING = 'processing', 'En traitement'
    COMPLETED = 'completed', 'Terminé'
    FAILED = 'failed', 'Échoué'
    REFUNDED = 'refunded', 'Remboursé'

class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Espèces'
    CIB = 'cib', 'Carte bancaire'
    EDAPHABIA = 'edahabia', 'Edahabia'
    CCP = 'ccp', 'CCP'
    WALLET = 'wallet', 'Portefeuille'

class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    trip_id = models.CharField(max_length=255, null=True, blank=True)
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    driver_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    block_reason = models.TextField(blank=True)
    user_id = models.IntegerField(db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    driver_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='DZD')
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    transaction_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    payment_gateway_response = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['booking_id']),
            models.Index(fields=['user_id']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Transaction {self.id} - {self.amount} DZD - {self.status}"
    
    def calculate_commission(self):
        """Calcule la commission de la plateforme (10%)"""
        self.commission = (self.amount * Decimal('0.10')).quantize(Decimal('0.01'))
        self.driver_amount = self.amount - self.commission
        return self.commission
class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(unique=True, db_index=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Wallet {self.user_id} - {self.balance} DZD"
    
    def add_balance(self, amount):
        self.balance += amount
        self.save()
        
    def subtract_balance(self, amount):
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            return True
        return False

class Refund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='refunds')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Refund {self.id} - {self.amount} DZD"