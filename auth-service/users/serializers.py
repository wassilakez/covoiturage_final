from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, Profile, RefreshToken, UserSession


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            'profile_picture', 'city', 'bio', 'driver_license_number',
            'verification_status', 'rating_as_driver', 'rating_as_passenger',
            'trips_as_driver', 'trips_as_passenger'
        ]
        read_only_fields = ['verification_status', 'rating_as_driver', 'rating_as_passenger']


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
            'phone', 'role', 'profile', 'is_verified', 'is_blocked',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'email', 'is_verified', 'is_blocked', 'date_joined', 'last_login']

    def get_full_name(self, obj):
        return obj.get_full_name()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    # Champs du véhicule pour les conducteurs
    vehicle_brand = serializers.CharField(write_only=True, required=False, allow_blank=True)
    vehicle_model = serializers.CharField(write_only=True, required=False, allow_blank=True)
    vehicle_year = serializers.CharField(write_only=True, required=False, allow_blank=True)
    vehicle_color = serializers.CharField(write_only=True, required=False, allow_blank=True)
    vehicle_license_plate = serializers.CharField(write_only=True, required=False, allow_blank=True)
    vehicle_seats = serializers.CharField(write_only=True, required=False, allow_blank=True)
    city = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone', 'role',
            'vehicle_brand', 'vehicle_model', 'vehicle_year', 
            'vehicle_color', 'vehicle_license_plate', 'vehicle_seats',
            'city'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas."})
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "Cet email est déjà utilisé."})
        phone = attrs.get('phone')
        if phone and User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError({"phone": "Ce numéro est déjà utilisé."})
        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError({"username": "Ce nom d'utilisateur est déjà pris."})
        return attrs

    def create(self, validated_data):
        # Extraire les champs du véhicule
        vehicle_brand = validated_data.pop('vehicle_brand', '')
        vehicle_model = validated_data.pop('vehicle_model', '')
        vehicle_year = validated_data.pop('vehicle_year', '')
        vehicle_color = validated_data.pop('vehicle_color', '')
        vehicle_license_plate = validated_data.pop('vehicle_license_plate', '')
        vehicle_seats = validated_data.pop('vehicle_seats', '')
        city = validated_data.pop('city', '')
        
        # Construire la bio à partir des infos véhicule
        bio_parts = []
        if vehicle_brand:
            bio_parts.append(f"Marque: {vehicle_brand}")
        if vehicle_model:
            bio_parts.append(f"Modèle: {vehicle_model}")
        if vehicle_year:
            bio_parts.append(f"Année: {vehicle_year}")
        if vehicle_color:
            bio_parts.append(f"Couleur: {vehicle_color}")
        if vehicle_license_plate:
            bio_parts.append(f"Plaque: {vehicle_license_plate}")
        if vehicle_seats:
            bio_parts.append(f"Places: {vehicle_seats}")
        
        bio = " - ".join(bio_parts) if bio_parts else ""
        
        # Extraire les autres champs
        validated_data.pop('password_confirm')
        phone = validated_data.pop('phone', None)
        
        # Créer l'utilisateur
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 'passenger'),
            phone=phone
        )
        
        # Mettre à jour le profil
        profile = user.profile
        if bio:
            profile.bio = bio
        if city:
            profile.city = city
        profile.save()
        
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(email=attrs['email'], password=attrs['password'])
        if not user:
            raise serializers.ValidationError("Email ou mot de passe incorrect.")
        if not user.is_active:
            raise serializers.ValidationError("Ce compte est désactivé.")
        if user.is_blocked:
            raise serializers.ValidationError(f"Compte bloqué : {user.blocked_reason or 'Non spécifiée'}")
        attrs['user'] = user
        return attrs


class UserPermissionsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    can_publish_trip = serializers.BooleanField()
    can_book_trip = serializers.BooleanField()
    is_blocked = serializers.BooleanField()
    is_verified = serializers.BooleanField()
    role = serializers.CharField()


class UserBasicInfoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField(allow_null=True)
    role = serializers.CharField()
    profile_picture = serializers.SerializerMethodField()
    city = serializers.CharField()
    bio = serializers.CharField()
    rating_as_driver = serializers.FloatField()
    rating_as_passenger = serializers.FloatField()
    trips_as_driver = serializers.IntegerField()
    trips_as_passenger = serializers.IntegerField()
    trips_completed = serializers.IntegerField()
    date_joined = serializers.DateTimeField()
    
    def get_profile_picture(self, obj):
        try:
            profile = obj.profile
            if profile.profile_picture and profile.profile_picture.name:
                pic_name = profile.profile_picture.name
                if pic_name.startswith('http://') or pic_name.startswith('https://'):
                    return pic_name
                elif 'https%3A' in pic_name or 'http%3A' in pic_name:
                    from urllib.parse import unquote
                    cleaned = pic_name.replace('/media/', '')
                    return unquote(cleaned)
                else:
                    return profile.profile_picture.url
        except (Profile.DoesNotExist, ValueError):
            pass
        return '/media/profiles/default.jpg'


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Les mots de passe ne correspondent pas."})
        return attrs


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = ['id', 'ip_address', 'user_agent', 'login_time', 'logout_time', 'is_active']
        read_only_fields = ['id', 'login_time']