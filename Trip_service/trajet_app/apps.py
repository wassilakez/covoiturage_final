 # trajet_app/apps.py
from django.apps import AppConfig
from django.conf import settings
import consul
import socket

class TrajetAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trajet_app'

    def ready(self):
        """
        This code runs automatically when the Django server starts.
        It registers the service with Consul for service discovery.
        """
        # Use try/except to prevent the server from crashing if Consul is not running
        try:
            c = consul.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)
            
            # Service information
            service_name = "trajet-service"
            service_id = "trajet-v1"
            
            # Register the service with Consul
            c.agent.service.register(
                name=service_name,
                service_id=service_id,
                address="127.0.0.1",  # Local machine address
                port=8002,            # Port where Trip Service runs
                # Health check: Consul will verify the /health/ endpoint every 10 seconds
                check=consul.Check.http("http://127.0.0.1:8002/api/health/", interval="10s")
            )
            print("✅ Successfully registered with Consul")
        except Exception as e:
            print(f"❌ Consul registration failed: {e}")