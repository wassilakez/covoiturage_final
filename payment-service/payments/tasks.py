# payments/tasks.py
from .models import Transaction, Wallet, PaymentStatus, Refund
import json
import logging
from celery import shared_task
from django.conf import settings
from .models import Transaction, Wallet, PaymentStatus
from .invoice import generate_pdf_receipt

logger = logging.getLogger(__name__)

class RabbitMQClient:
    """Client pour interagir avec RabbitMQ"""
    
    def __init__(self):
        try:
            import pika
            self.pika = pika
            self.connection_params = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                credentials=pika.PlainCredentials(
                    settings.RABBITMQ_USER,
                    settings.RABBITMQ_PASSWORD
                )
            )
        except ImportError:
            logger.warning("pika not installed, RabbitMQ disabled")
            self.pika = None
    
    def publish_message(self, queue, message):
        """Publier un message dans une queue"""
        if not self.pika:
            logger.info(f"Simulation: Message publié dans {queue}: {message}")
            return True
            
        try:
            connection = self.pika.BlockingConnection(self.connection_params)
            channel = connection.channel()
            
            channel.queue_declare(queue=queue, durable=True)
            
            channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=json.dumps(message),
                properties=self.pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            
            connection.close()
            logger.info(f"Message publié dans {queue}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur publication RabbitMQ: {str(e)}")
            return False

@shared_task
def process_payment_confirmation(transaction_id):
    """Tâche asynchrone pour traiter une confirmation de paiement"""
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        # Mettre à jour le statut
        transaction.status = PaymentStatus.COMPLETED
        transaction.completed_at = transaction.completed_at.now()
        transaction.save()
        
        # Générer le reçu PDF
        receipt_path = generate_pdf_receipt(transaction)
        
        # Publier un message pour le Booking Service
        rabbitmq = RabbitMQClient()
        message = {
            'event': 'payment_confirmed',
            'transaction_id': str(transaction.id),
            'booking_id': str(transaction.booking_id),
            'user_id': str(transaction.user_id),
            'amount': float(transaction.amount),
            'status': 'confirmed',
            'timestamp': transaction.completed_at.isoformat()
        }
        
        rabbitmq.publish_message(
            queue='booking_queue',
            message=message
        )
        
        return {
            'success': True,
            'transaction_id': str(transaction.id),
            'receipt_path': receipt_path
        }
        
    except Exception as e:
        logger.error(f"Erreur traitement paiement: {str(e)}")
        return {'success': False, 'error': str(e)}

@shared_task
def process_wallet_payment(transaction_id):
    """Traitement des paiements par portefeuille"""
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        wallet = Wallet.objects.get(user_id=transaction.user_id)
        
        if wallet.subtract_balance(transaction.amount):
            # Paiement réussi
            result = process_payment_confirmation(transaction_id)
            return result
        else:
            # Solde insuffisant
            transaction.status = PaymentStatus.FAILED
            transaction.failure_reason = "Solde insuffisant"
            transaction.save()
            
            return {'success': False, 'error': 'Solde insuffisant'}
            
    except Exception as e:
        logger.error(f"Erreur paiement wallet: {str(e)}")
        return {'success': False, 'error': str(e)}

@shared_task
def process_refund(transaction_id, reason):
    """Tâche asynchrone pour traiter un remboursement"""
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        if transaction.status != PaymentStatus.COMPLETED:
            raise Exception("Seules les transactions complétées peuvent être remboursées")
        
        # Mettre à jour le statut
        transaction.status = PaymentStatus.REFUNDED
        transaction.save()
        
        # Créer un remboursement
        refund = Refund.objects.create(
            transaction=transaction,
            amount=transaction.amount - transaction.commission,
            reason=reason,
            status='completed'
        )
        
        return {
            'success': True,
            'refund_id': str(refund.id),
            'amount': float(refund.amount)
        }
        
    except Exception as e:
        logger.error(f"Erreur remboursement: {str(e)}")
        return {'success': False, 'error': str(e)}