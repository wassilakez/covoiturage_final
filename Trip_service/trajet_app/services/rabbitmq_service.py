# trajet_app/services/rabbitmq_service.py
import pika
import json
from django.conf import settings

def publish_ride_created(ride_data):
    
    try:
        # الاتصال بـ RabbitMQ باستخدام العنوان الموجود في settings
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=settings.RABBITMQ_HOST)
        )
        channel = connection.channel()

        # إنشاء طابور (Queue) يسمى 'rides_queue'
        channel.queue_declare(queue='rides_queue')

        # تحويل البيانات إلى صيغة JSON وإرسالها
        message = json.dumps(ride_data)
        channel.basic_publish(
            exchange='',
            routing_key='rides_queue',
            body=message
        )
        
        print(f" [x] Sent to RabbitMQ: {message}")
        connection.close()
    except Exception as e:
        print(f" [!] Failed to connect to RabbitMQ: {e}")