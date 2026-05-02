import pika
import json

connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
channel = connection.channel()
channel.queue_declare(queue='notifications', durable=True)

message = {"type": "test", "message": "Hello Caravan"}

channel.basic_publish(exchange='', routing_key='notifications', body=json.dumps(message))
connection.close()
print("✅ Message envoyé")