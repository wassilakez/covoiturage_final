# payments/consumers.py

import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """
    Client RabbitMQ pour publier des messages
    """
    
    def __init__(self, host=None, port=None, user=None, password=None):
        self.host = host or getattr(settings, 'RABBITMQ_HOST', 'localhost')
        self.port = port or getattr(settings, 'RABBITMQ_PORT', 5672)
        self.user = user or getattr(settings, 'RABBITMQ_USER', 'guest')
        self.password = password or getattr(settings, 'RABBITMQ_PASSWORD', 'guest')
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
            logger.info(f"[SIMULATION] Message publié dans {queue}: {message.get('event', 'unknown')}")
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
    """
    
    def __init__(self, host=None, port=None, user=None, password=None):
        self.host = host or getattr(settings, 'RABBITMQ_HOST', 'localhost')
        self.port = port or getattr(settings, 'RABBITMQ_PORT', 5672)
        self.user = user or getattr(settings, 'RABBITMQ_USER', 'guest')
        self.password = password or getattr(settings, 'RABBITMQ_PASSWORD', 'guest')
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
    
    def callback(self, ch, method, properties, body):
        """Callback pour traiter les messages reçus"""
        try:
            message = json.loads(body)
            event_type = message.get('event')
            logger.info(f"Message reçu: {event_type}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Erreur traitement message: {e}")
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
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue='payment_queue', on_message_callback=self.callback)
        
        logger.info("Payment Consumer démarré. En attente de messages...")
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Arrêt demandé")
            self.stop()
    
    def stop(self):
        """Arrêter le consumer"""
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