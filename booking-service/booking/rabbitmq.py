import pika
import json
import os

def send_booking_event(data):
    host = os.getenv('RABBITMQ_HOST', 'localhost')
    
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=host)
    )
    
    channel = connection.channel()
    channel.queue_declare(queue='booking_queue', durable=True)
    
    channel.basic_publish(
        exchange='',
        routing_key='booking_queue',
        body=json.dumps(data),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    
    connection.close()
    print(f"✅ Événement envoyé à RabbitMQ ({host}): {data.get('event')}")