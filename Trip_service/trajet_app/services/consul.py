# api_app/services/consul.py

import consul
import socket
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def register_service():
    """Register this service with Consul"""
    try:
        c = consul.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)
        
        service_host = socket.gethostbyname(socket.gethostname())
        
        c.agent.service.register(
            name='api-service',
            service_id='api-service-1',
            address=service_host,
            port=8002,
            tags=['api', 'django'],
            check=consul.Check.http(
                f'http://{service_host}:8002/api/health/',
                interval='10s',
                timeout='5s'
            )
        )
        
        logger.info("API Service registered with Consul")
        
    except Exception as e:
        logger.error(f"Failed to register with Consul: {e}")


def deregister_service():
    """Deregister this service from Consul"""
    try:
        c = consul.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)
        c.agent.service.deregister('api-service-1')
        logger.info("API Service deregistered from Consul")
    except Exception as e:
        logger.error(f"Failed to deregister: {e}")