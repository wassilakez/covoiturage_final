import requests
import re
from django.conf import settings
from django.http import JsonResponse

class JWTAuthenticationMiddleware:
    """Verify JWT token by communicating with Auth Service"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # 1. List of public endpoints (no authentication required)
        # Using r'^...$' for precise route matching
        public_paths = [
            r'^/api/health/$',            # Important for Consul Service Discovery
            r'^/api/cities/$',            # List of cities (for Algeria)
            r'^/api/rides/$',             # Display available rides for everyone
            r'^/api/rides/\d+/$',         # Display specific ride details (numeric ID)
            r'^/api/search/$',            # Ride search engine
            r'^/admin/.*$',               # Admin panel routes
        ]
        
        current_path = request.path
        
        # 2. Check if the requested URL is public
        for path_pattern in public_paths:
            if re.match(path_pattern, current_path):
                return self.get_response(request)
        
        # 3. If the endpoint is protected, look for the token in the Header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return JsonResponse({'error': 'No token provided'}, status=401)
        
        try:
            # Extract token (expected format: Bearer <token>)
            token = auth_header.split(' ')[1]
        except IndexError:
            return JsonResponse({'error': 'Invalid token format. Use: Bearer <token>'}, status=401)
        
        # 4. Verify the token by making an internal request to Auth Service
        try:
            # Send token to Auth Service to verify identity and permissions
            response = requests.get(
                f"{settings.AUTH_SERVICE_URL}/auth/verify/",
                headers={'Authorization': f'Bearer {token}'},
                timeout=5
            )
            
            if response.status_code == 200:
                # If token is valid, receive user data and store it in the request
                user_data = response.json()
                request.user_id = user_data.get('user_id')
                request.username = user_data.get('username')
                request.user_type = user_data.get('user_type')
                request.email = user_data.get('email')
                
                return self.get_response(request)
            else:
                return JsonResponse({'error': 'Invalid or expired token'}, status=401)
                
        except requests.exceptions.RequestException:
            # If Auth Service is unavailable
            return JsonResponse({'error': 'Auth service is down or unreachable'}, status=503)