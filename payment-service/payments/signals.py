# payments/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Transaction, PaymentStatus
from .tasks import process_payment_confirmation, process_wallet_payment

@receiver(post_save, sender=Transaction)
def transaction_post_save(sender, instance, created, **kwargs):
    """
    Signal déclenché après la sauvegarde d'une transaction
    """
    if created:
        # Nouvelle transaction créée
        if instance.payment_method == 'wallet':
            # Traitement immédiat pour le wallet
            process_wallet_payment.delay(str(instance.id))
            
    else:
        # Transaction mise à jour
        if instance.status == PaymentStatus.PROCESSING:
            # Si le statut passe à processing, lancer la confirmation
            process_payment_confirmation.delay(str(instance.id))