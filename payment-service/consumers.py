# consumers.py - À la RACINE du projet payment-service
# Chemin: C:\Users\dell\payment-service\consumers.py

import json
import logging
import threading
import time
import os
import sys

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration Django pour pouvoir utiliser les modèles
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payment_project.settings')

# Initialiser Django
import django
django.setup()

# Maintenant on peut importer les modèles Django
from payments.models import Transaction, Wallet, PaymentStatus
from payments.tasks import process_payment_confirmation, process_refund


class RabbitMQClient:
    """
    Client RabbitMQ pour publier des messages
    """
    
    def __init__(self, host='localhost', port=5672, user='guest', password='guest'):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.connection = None
        self.channel = None
        self.connected = False
        self.pika = None
        
        try:
            import pika
            self.pika = pika
            logger.info("Bibliothèque pika chargée avec succès")
        except ImportError as e:
            logger.warning(f"pika non installé: {e}")
            logger.warning("RabbitMQ sera simulé")
    
    def connect(self):
        """Établir la connexion à RabbitMQ"""
        if not self.pika:
            return False
            
        try:
            credentials = self.pika.PlainCredentials(self.user, self.password)
            parameters = self.pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = self.pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.connected = True
            logger.info(f"Connecté à RabbitMQ sur {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Erreur connexion RabbitMQ: {e}")
            self.connected = False
            return False
    
    def publish_message(self, queue, message, exchange=''):
        """
        Publier un message dans une queue RabbitMQ
        
        Args:
            queue: Nom de la queue
            message: Message à publier (dictionnaire)
            exchange: Exchange (vide par défaut)
        """
        if not self.pika or not self.connect():
            # Mode simulation
            logger.info(f"[SIMULATION] Message publié dans {queue}: {json.dumps(message, indent=2)}")
            return True
        
        try:
            # Déclarer la queue (durable pour persistance)
            self.channel.queue_declare(queue=queue, durable=True)
            
            # Publier le message
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=queue,
                body=json.dumps(message, ensure_ascii=False),
                properties=self.pika.BasicProperties(
                    delivery_mode=2,  # Message persistant
                    content_type='application/json'
                )
            )
            
            logger.info(f"Message publié dans {queue}: {message.get('event', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur publication: {e}")
            return False
        finally:
            if self.connection:
                self.connection.close()
                self.connected = False
    
    def close(self):
        """Fermer la connexion"""
        if self.connection and self.connection.is_open:
            self.connection.close()
            self.connected = False


class PaymentConsumer:
    """
    Consommateur RabbitMQ pour le Payment Service
    Écoute les événements des autres services (Booking, etc.)
    """
    
    def __init__(self, host='localhost', port=5672, user='guest', password='guest'):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.connection = None
        self.channel = None
        self.should_stop = False
        self.pika = None
        
        try:
            import pika
            self.pika = pika
        except ImportError:
            logger.error("pika non installé, impossible de démarrer le consumer")
            self.pika = None
    
    def connect(self):
        """Établir la connexion à RabbitMQ"""
        if not self.pika:
            return False
            
        try:
            credentials = self.pika.PlainCredentials(self.user, self.password)
            parameters = self.pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = self.pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info(f"Consumer connecté à RabbitMQ sur {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Erreur connexion consumer: {e}")
            return False
    
    def declare_queues(self):
        """Déclarer les queues nécessaires"""
        queues = ['payment_queue', 'booking_queue', 'notification_queue']
        for queue in queues:
            self.channel.queue_declare(queue=queue, durable=True)
            logger.info(f"Queue déclarée: {queue}")
    
    def handle_booking_confirmed(self, message):
        """
        Gérer l'événement de réservation confirmée
        Crée automatiquement une transaction en attente
        """
        try:
            booking_id = message.get('booking_id')
            user_id = message.get('user_id')
            amount = message.get('amount')
            metadata = message.get('metadata', {})
            
            logger.info(f"Réservation confirmée reçue: {booking_id}")
            
            # Vérifier si un paiement existe déjà
            existing = Transaction.objects.filter(
                booking_id=booking_id,
                status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING]
            ).first()
            
            if existing:
                logger.info(f"Paiement déjà existant pour {booking_id}")
                return
            
            # Créer une transaction en attente
            transaction = Transaction.objects.create(
                booking_id=booking_id,
                user_id=user_id,
                amount=amount,
                payment_method='pending',  # Méthode non encore choisie
                status=PaymentStatus.PENDING,
                metadata=metadata
            )
            
            logger.info(f"Transaction créée: {transaction.id}")
            
        except Exception as e:
            logger.error(f"Erreur handle_booking_confirmed: {e}")
    
    def handle_booking_cancelled(self, message):
        """
        Gérer l'événement de réservation annulée
        Lance automatiquement un remboursement si paiement effectué
        """
        try:
            booking_id = message.get('booking_id')
            reason = message.get('reason', 'Annulation de réservation')
            
            logger.info(f"Réservation annulée reçue: {booking_id}")
            
            # Chercher la transaction
            transaction = Transaction.objects.filter(
                booking_id=booking_id,
                status=PaymentStatus.COMPLETED
            ).first()
            
            if transaction:
                logger.info(f"Remboursement lancé pour {booking_id}")
                # Lancer le remboursement asynchrone
                process_refund.delay(str(transaction.id), reason)
            else:
                logger.info(f"Aucun paiement trouvé pour {booking_id}")
                
        except Exception as e:
            logger.error(f"Erreur handle_booking_cancelled: {e}")
    
    def handle_payment_status_request(self, message):
        """
        Gérer une demande de statut de paiement
        Répond avec le statut actuel
        """
        try:
            booking_id = message.get('booking_id')
            reply_to = message.get('reply_to', 'booking_queue')
            
            logger.info(f"Demande statut paiement pour {booking_id}")
            
            transaction = Transaction.objects.filter(booking_id=booking_id).first()
            
            response = {
                'event': 'payment_status_response',
                'booking_id': booking_id,
                'has_payment': transaction is not None,
                'status': transaction.status if transaction else None,
                'amount': float(transaction.amount) if transaction else None,
                'transaction_id': str(transaction.id) if transaction else None
            }
            
            # Publier la réponse
            client = RabbitMQClient(self.host, self.port, self.user, self.password)
            client.publish_message(reply_to, response)
            
        except Exception as e:
            logger.error(f"Erreur handle_payment_status_request: {e}")
    
    def callback(self, ch, method, properties, body):
        """
        Callback pour traiter les messages reçus
        """
        try:
            message = json.loads(body)
            event_type = message.get('event')
            
            logger.info(f"Message reçu: {event_type}")
            
            # Traiter selon le type d'événement
            if event_type == 'booking_confirmed':
                self.handle_booking_confirmed(message)
                
            elif event_type == 'booking_cancelled':
                self.handle_booking_cancelled(message)
                
            elif event_type == 'payment_status_request':
                self.handle_payment_status_request(message)
            
            elif event_type == 'booking_paid':
                logger.info(f"Booking déjà payé: {message.get('booking_id')}")
            
            else:
                logger.warning(f"Événement non reconnu: {event_type}")
            
            # Accuser réception du message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except json.JSONDecodeError as e:
            logger.error(f"Erreur décodage JSON: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Erreur traitement message: {e}")
            # Rejeter et remettre dans la queue
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Démarrer la consommation des messages"""
        if not self.pika:
            logger.error("Impossible de démarrer: pika non installé")
            return
        
        if not self.connect():
            logger.error("Impossible de se connecter à RabbitMQ")
            return
        
        self.declare_queues()
        
        # Configurer la qualité de service
        self.channel.basic_qos(prefetch_count=1)
        
        # Commencer à écouter
        self.channel.basic_consume(
            queue='payment_queue',
            on_message_callback=self.callback
        )
        
        logger.info("Payment Consumer démarré. En attente de messages...")
        logger.info("Appuyez sur Ctrl+C pour arrêter")
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Arrêt demandé par l'utilisateur")
            self.stop()
        except Exception as e:
            logger.error(f"Erreur dans le consumer: {e}")
            self.stop()
    
    def stop(self):
        """Arrêter le consumer"""
        self.should_stop = True
        if self.channel:
            try:
                self.channel.stop_consuming()
            except:
                pass
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
        logger.info("Consumer arrêté")


def start_payment_consumer():
    """
    Fonction pour démarrer le consumer dans un thread séparé
    Utilisable depuis manage.py ou un script
    """
    # Récupérer la configuration depuis les variables d'environnement
    host = os.environ.get('RABBITMQ_HOST', 'localhost')
    port = int(os.environ.get('RABBITMQ_PORT', 5672))
    user = os.environ.get('RABBITMQ_USER', 'guest')
    password = os.environ.get('RABBITMQ_PASSWORD', 'guest')
    
    consumer = PaymentConsumer(host, port, user, password)
    consumer.start_consuming()


def test_rabbitmq_connection():
    """Tester la connexion à RabbitMQ"""
    client = RabbitMQClient()
    if client.connect():
        logger.info("✅ Connexion RabbitMQ réussie")
        client.close()
        return True
    else:
        logger.error("❌ Connexion RabbitMQ échouée")
        return False


# Point d'entrée pour exécuter directement le script
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Payment Service RabbitMQ Consumer')
    parser.add_argument('--test', action='store_true', help='Tester la connexion RabbitMQ')
    parser.add_argument('--host', default='localhost', help='RabbitMQ host')
    parser.add_argument('--port', type=int, default=5672, help='RabbitMQ port')
    
    args = parser.parse_args()
    
    if args.test:
        test_rabbitmq_connection()
    else:
        # Démarrer le consumer
        print("=== Payment Service RabbitMQ Consumer ===")
        print(f"Host: {args.host}")
        print(f"Port: {args.port}")
        print("=" * 40)
        
        consumer = PaymentConsumer(args.host, args.port)
        consumer.start_consuming()