from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model

User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
def sync_user(request):
    data = request.data
    user_id = data.get('id')
    
    if not user_id:
        return Response({'error': 'id required'}, status=400)
    
    # 🔧 CORRECTION : username ne peut pas être null
    username = data.get('username', f'user_{user_id}')
    # Nettoyer le username (enlever caractères spéciaux, espaces)
    username = ''.join(c for c in username if c.isalnum() or c == '_')
    if not username:
        username = f'user_{user_id}'
    
    email = data.get('email', f'user_{user_id}@temp.com')
    
    user, created = User.objects.get_or_create(
        id=user_id,
        defaults={
            'username': username,
            'email': email,
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
        }
    )
    
    if not created:
        if data.get('username'):
            new_username = ''.join(c for c in data.get('username') if c.isalnum() or c == '_')
            if new_username:
                user.username = new_username
        if data.get('email'):
            user.email = data.get('email')
        if data.get('first_name'):
            user.first_name = data.get('first_name')
        if data.get('last_name'):
            user.last_name = data.get('last_name')
        user.save()
    
    return Response({'status': 'ok', 'created': created, 'id': user.id})