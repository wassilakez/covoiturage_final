from django.core.management.base import BaseCommand
from notifications.consumer import start_consuming
import time

class Command(BaseCommand):
    help = 'Start RabbitMQ consumer'
    
    def handle(self, *args, **options):
        self.stdout.write("Starting RabbitMQ consumer...")
        for attempt in range(5):
            try:
                start_consuming()
                break
            except Exception as e:
                self.stderr.write(f"Error: {e}")
                time.sleep(5)