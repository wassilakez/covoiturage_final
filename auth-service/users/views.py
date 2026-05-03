import socket
import requests
import uuid
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import User, Profile, RefreshToken, UserSession
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer, 
    UserPermissionsSerializer, UserBasicInfoSerializer,
    ProfileSerializer, ChangePasswordSerializer, UserSessionSerializer
)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        def optional_int(field_name):
            value = request.data.get(field_name)
            if value in (None, ''):
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Sauvegarde city et bio dans le profil
            profile = user.profile
            city = request.data.get('city', '')
            bio = request.data.get('bio', '')
            if city:
                profile.city = city
            if bio:
                profile.bio = bio
            profile.save()
            
            # Sauvegarde des infos véhicule
            user.vehicle_brand = request.data.get('vehicle_brand', '')
            user.vehicle_model = request.data.get('vehicle_model', '')
            user.vehicle_year = optional_int('vehicle_year')
            user.vehicle_color = request.data.get('vehicle_color', '')
            user.vehicle_license_plate = request.data.get('vehicle_license_plate', '')
            user.vehicle_seats = optional_int('vehicle_seats')
            user.save()
            
                        # ✅ SAUVEGARDE PHOTO AVEC DJANGO (propre)
            profile_picture = request.FILES.get('profile_picture')
            if profile_picture:
                try:
                    # Django gère le nom, le chemin et la sauvegarde
                    profile.profile_picture = profile_picture
                    profile.save()
                    print(f"✅ Photo sauvegardée: {profile.profile_picture.url}")
                except Exception as e:
                    print(f"❌ Erreur sauvegarde photo: {e}")
            else:
                print("⚠️ Aucune photo fournie")
            
            refresh = JWTRefreshToken.for_user(user)
            UserSession.objects.create(
                user=user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                is_active=True
            )
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # ✅ Utiliser validated_data, PAS save()
            user = serializer.validated_data['user']
            user.last_login = timezone.now()
            user.save()
            
            refresh = JWTRefreshToken.for_user(user)
            UserSession.objects.create(
                user=user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                is_active=True
            )
            RefreshToken.objects.create(
                user=user,
                token=str(refresh),
                expires_at=timezone.now() + timezone.timedelta(days=7)
            )
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        session_id = request.data.get('session_id')
        if session_id:
            UserSession.objects.filter(id=session_id, user=request.user).update(
                logout_time=timezone.now(), is_active=False
            )
        refresh_token = request.data.get('refresh')
        if refresh_token:
            RefreshToken.objects.filter(token=refresh_token).update(revoked=True)
        return Response({'message': 'Déconnexion réussie'})

class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            'user': UserSerializer(request.user).data,
            'profile': ProfileSerializer(request.user.profile).data
        })

class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({'old_password': 'Ancien mot de passe incorrect.'}, status=400)
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'message': 'Mot de passe modifié avec succès.'})
        return Response(serializer.errors, status=400)

class MySessionsView(generics.ListAPIView):
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user, is_active=True)

class UserPermissionsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            return Response({
                'id': user.id,
                'can_publish_trip': user.can_publish_trip(),
                'can_book_trip': user.can_book_trip(),
                'is_blocked': user.is_blocked,
                'is_verified': user.is_verified,
                'role': user.role
            })
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur non trouvé'}, status=404)

class UserBasicInfoView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            profile = user.profile
            
            return Response({
                'id': user.id,
                'full_name': user.get_full_name(),
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'email': user.email,
                'phone': user.phone,
                'role': user.role,
                'profile_picture': profile.profile_picture.url if profile.profile_picture else '/media/profiles/default.jpg',
                'city': profile.city or '',
                'bio': profile.bio or '',
                'date_joined': user.date_joined,
                'rating_as_driver': float(profile.rating_as_driver),
                'rating_as_passenger': float(profile.rating_as_passenger),
                'trips_as_driver': profile.trips_as_driver,
                'trips_as_passenger': profile.trips_as_passenger,
                'trips_completed': profile.trips_completed,
                'vehicle_brand': user.vehicle_brand or '',
                'vehicle_model': user.vehicle_model or '',
                'vehicle_year': user.vehicle_year,
                'vehicle_color': user.vehicle_color or '',
                'vehicle_license_plate': user.vehicle_license_plate or '',
                'vehicle_seats': user.vehicle_seats,
            })
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur non trouvé'}, status=404)

class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return JsonResponse({
            "status": "healthy",
            "service": "auth-service",
            "server": socket.gethostbyname(socket.gethostname()),
            "database": "connected",
            "timestamp": timezone.now().isoformat()
        })

class UploadView(APIView):
    permission_classes = [permissions.AllowAny]  # ← CHANGER ICI
    
    def post(self, request):
        user_id = request.data.get('user_id') or request.POST.get('user_id')
        profile_picture = request.FILES.get('profile_picture') or request.FILES.get('file')
        
        if not user_id:
            return Response({'error': 'user_id requis'}, status=400)
        
        if not profile_picture:
            return Response({'error': 'Aucun fichier fourni'}, status=400)
        
        try:
            user = User.objects.get(id=user_id)
            profile = Profile.objects.get(user=user)
            
            # Supprimer l'ancienne photo si elle n'est pas par défaut
            if profile.profile_picture and 'default' not in profile.profile_picture.name:
                profile.profile_picture.delete(save=False)
            
            # Sauvegarder la nouvelle photo
            ext = profile_picture.name.split('.')[-1].lower()
            new_name = f"user_{user.id}_profile_{uuid.uuid4().hex[:8]}.{ext}"
            profile.profile_picture.save(new_name, profile_picture)
            profile.save()
            
            return Response({
                'status': 'success',
                'profile_picture_url': profile.profile_picture.url
            })
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur non trouvé'}, status=404)
        except Profile.DoesNotExist:
            return Response({'error': 'Profil non trouvé'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

def home_page(request):
    return render(request, 'base.html')

def register_page(request):
    return render(request, 'register.html')

def login_page(request):
    return render(request, 'login.html')

@login_required
def profile_page(request):
    user = request.user
    profile = user.profile
    
    user_data = {
        'id': user.id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'username': user.username,
        'email': user.email,
        'phone': user.phone or '',
        'role': user.role,
        'profile_picture': profile.profile_picture.url if profile.profile_picture else None,
        'city': profile.city or '',
        'bio': profile.bio or '',
        'date_joined': user.date_joined,
        'rating_as_driver': float(profile.rating_as_driver) if profile.rating_as_driver else 0,
        'rating_as_passenger': float(profile.rating_as_passenger) if profile.rating_as_passenger else 0,
        'trips_as_driver': profile.trips_as_driver or 0,
        'trips_as_passenger': profile.trips_as_passenger or 0,
        'trips_completed': profile.trips_completed or 0,
        'vehicle_brand': getattr(user, 'vehicle_brand', '') or '',
        'vehicle_model': getattr(user, 'vehicle_model', '') or '',
        'vehicle_year': getattr(user, 'vehicle_year', None),
        'vehicle_color': getattr(user, 'vehicle_color', '') or '',
        'vehicle_license_plate': getattr(user, 'vehicle_license_plate', '') or '',
        'vehicle_seats': getattr(user, 'vehicle_seats', None),
    }
    
    return render(request, 'profile.html', {'user': user_data})

@login_required
def dashboard_page(request):
    return render(request, 'dashboard.html')
