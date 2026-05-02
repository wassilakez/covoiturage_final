# api_app/services/rabbitmq.py

import pika
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def publish_booking_notification(booking_id, passenger_id, ride_id):
    """Publish booking confirmation to RabbitMQ"""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=settings.RABBITMQ_HOST)
        )
        channel = connection.channel()
        
        channel.queue_declare(queue='notifications', durable=True)
        
        message = {
            'type': 'booking_confirmation',
            'booking_id': booking_id,
            'passenger_id': passenger_id,
            'ride_id': ride_id,
            'timestamp': str(import_datetime()),
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='notifications',
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )
        
        connection.close()
        logger.info(f"Published booking notification for booking {booking_id}")
        
    except Exception as e:
        logger.error(f"Failed to publish notification: {e}")


def import_datetime():
    from django.utils import timezone
    return timezone.now()