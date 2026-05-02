# manage_rabbitmq.py

#!/usr/bin/env python
import pika
import sys
import json
from django.conf import settings

def check_rabbitmq():
    """Vérifier la connexion RabbitMQ"""
    try:
        params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=pika.PlainCredentials(
                settings.RABBITMQ_USER,
                settings.RABBITMQ_PASSWORD
            )
        )
        connection = pika.BlockingConnection(params)
        connection.close()
        print("✅ RabbitMQ est accessible")
        return True
    except Exception as e:
        print(f"❌ RabbitMQ inaccessible: {e}")
        return False

def list_queues():
    """Lister les queues"""
    try:
        params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=pika.PlainCredentials(
                settings.RABBITMQ_USER,
                settings.RABBITMQ_PASSWORD
            )
        )
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        queues = ['payment_queue', 'booking_queue', 'notification_queue']
        
        for queue in queues:
            try:
                result = channel.queue_declare(queue=queue, durable=True, passive=True)
                print(f"Queue '{queue}': {result.method.message_count} messages")
            except:
                print(f"Queue '{queue}': n'existe pas")
        
        connection.close()
        
    except Exception as e:
        print(f"Erreur: {e}")

def purge_queue(queue_name):
    """Vider une queue"""
    try:
        params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=pika.PlainCredentials(
                settings.RABBITMQ_USER,
                settings.RABBITMQ_PASSWORD
            )
        )
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        result = channel.queue_purge(queue=queue_name)
        print(f"Queue '{queue_name}': {result.method.message_count} messages purgés")
        
        connection.close()
        
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage_rabbitmq.py [check|list|purge queue_name]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "check":
        check_rabbitmq()
    elif command == "list":
        list_queues()
    elif command == "purge" and len(sys.argv) > 2:
        purge_queue(sys.argv[2])
    else:
        print("Commande non reconnue")