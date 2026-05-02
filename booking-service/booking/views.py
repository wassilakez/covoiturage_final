import requests
import uuid
from datetime import datetime
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db import transaction, models
from django.conf import settings
from .models import Booking, Rating
from .serializers import BookingSerializer, RatingSerializer
from .rabbitmq import send_booking_event
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny
from django.utils import timezone


User = get_user_model()


@api_view(['POST'])
@permission_classes([AllowAny])
def sync_user(request):
    data = request.data
    user_id = data.get('id')
    
    if not user_id:
        return Response({'error': 'id required'}, status=400)
    
    user, created = User.objects.get_or_create(
        id=user_id,
        defaults={
            'username': data.get('username', f'user{user_id}'),
            'email': data.get('email', f'user{user_id}@temp.com'),
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
        }
    )
    
    if not created:
        if data.get('username'):
            user.username = data.get('username')
        if data.get('email'):
            user.email = data.get('email')
        if data.get('first_name'):
            user.first_name = data.get('first_name')
        if data.get('last_name'):
            user.last_name = data.get('last_name')
        user.save()
    
    return Response({'status': 'ok', 'created': created, 'id': user.id})


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer

    def get_queryset(self):
        queryset = Booking.objects.all()
        user_id = self.request.query_params.get('user_id')
        driver_id = self.request.query_params.get('driver_id')
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if driver_id:
            queryset = queryset.filter(driver_id=driver_id)
            
        return queryset

    def _verify_user_exists(self, user_id):
        try:
            url = f"{settings.USERS_SERVICE_URL}/users/{user_id}/basic/"
            print(f"🔍 Vérification utilisateur: {url}")
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return True, response.json()
            return False, None
        except Exception as e:
            print(f"⚠️ Erreur Auth: {e}")
            return False, None

    def _verify_trip_exists(self, trip_id, seats_requested):
        try:
            url = f"{settings.TRIPS_SERVICE_URL}/trips/{trip_id}"
            print(f"🔍 Vérification trajet: {url}")
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                return False, None, f"Trip not found (HTTP {response.status_code})"
            
            trip_data = response.json()
            available_seats = trip_data.get('available_seats', 0)
            departure_datetime = trip_data.get('departure_datetime')
            
            # Vérification date dépassée
            if departure_datetime:
                try:
                    trip_date_str = departure_datetime[:10] if len(departure_datetime) >= 10 else ''
                    if trip_date_str:
                        trip_date = datetime.strptime(trip_date_str, '%Y-%m-%d').date()
                        today = datetime.now().date()
                        
                        print(f"Date trajet: {trip_date}, Date aujourd'hui: {today}")
                        
                        if trip_date < today:
                            return False, trip_data, "❌ Ce trajet a déjà eu lieu. Réservation impossible."
                except Exception as e:
                    print(f"⚠️ Erreur parsing date: {e}")
            
            if seats_requested > available_seats:
                return False, trip_data, f"❌ Seulement {available_seats} places disponibles"
            
            return True, trip_data, None
        except Exception as e:
            return False, None, f"Erreur Trip service: {str(e)}"

    def create(self, request, *args, **kwargs):
        print(f"🔍 Données reçues par booking-service: {request.data}")
        user_id = request.data.get('user_id')
        trip_id = request.data.get('trip_id')
        driver_id = request.data.get('driver_id')
        seats_requested = int(request.data.get('seats_booked', 1))
        payment_method = request.data.get('payment_method', 'cash')
        amount = request.data.get('amount', 0)
        transaction_id = request.data.get('transaction_id', None)

        if not user_id or not trip_id:
            return Response(
                {'error': 'user_id et trip_id sont requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Vérification double réservation
        existing_booking = Booking.objects.filter(
            user_id=user_id,
            trip_id=trip_id,
            status__in=['pending', 'confirmed', 'completed']
        ).first()
        
        if existing_booking:
            return Response(
                {'error': f'❌ Vous avez déjà une réservation active pour ce trajet (statut: {existing_booking.status}). Annulez-la d\'abord.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_exists, user_data = self._verify_user_exists(user_id)
        if not user_exists:
            return Response(
                {'error': f'❌ Utilisateur {user_id} non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )

        trip_exists, trip_data, trip_error = self._verify_trip_exists(trip_id, seats_requested)
        if not trip_exists:
            return Response(
                {'error': f'❌ {trip_error}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            status_value = request.data.get('status', 'pending')

            booking = Booking.objects.create(
                user_id=user_id,
                trip_id=trip_id,
                driver_id=driver_id,
                seats_booked=seats_requested,
                payment_method=payment_method,
                amount=amount,
                status=status_value,
                passenger_confirmed=False,
                driver_confirmed=False,
                transaction_id=transaction_id
            )
            
            # Mettre à jour les places disponibles
            try:
                available_seats = trip_data.get('available_seats', 0)
                new_available = available_seats - seats_requested
                update_response = requests.patch(
                    f"{settings.TRIPS_SERVICE_URL}/trips/{trip_id}/",
                    json={'available_seats': new_available},
                    timeout=5
                )
                if update_response.status_code == 200:
                    print(f"✅ Places mises à jour: {available_seats} -> {new_available}")
                else:
                    print(f"⚠️ Erreur mise à jour places: {update_response.status_code}")
            except Exception as e:
                print(f"⚠️ Erreur mise à jour places: {e}")
            
            # Paiement par carte (port 8000)
            if payment_method != 'cash':
                try:
                    payment_response = requests.post(
                        "http://payment-service:8084/api/payments/create/",
                        json={
                            'user_id': user_id,
                            'amount': float(amount),
                            'payment_method': payment_method,
                            'booking_id': str(booking.id),
                            'trip_id': trip_id
                        },
                        timeout=10
                    )
                    print(f"💰 Payment response: {payment_response.status_code}")
                    if payment_response.status_code in [200, 201]:
                        payment_data = payment_response.json()
                        booking.transaction_id = payment_data.get('transaction_id')
                        booking.save()
                        print(f"✅ Transaction créée: {booking.transaction_id} (argent bloqué)")
                    else:
                        print(f"⚠️ Erreur payment: {payment_response.status_code}")
                except Exception as e:
                    print(f"⚠️ Erreur payment-service: {e}")
                    
        try:
            send_booking_event({
                "event": "booking_created",
                "bookingId": booking.id,
                "userId": user_id,
                "tripId": trip_id,
                "driverId": driver_id,
                "seats": seats_requested,
                "paymentMethod": payment_method,
                "status": booking.status
            })
        except Exception as e:
            print(f"⚠️ RabbitMQ: {e}")

        serializer = BookingSerializer(booking)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def confirm_by_driver(self, request, pk=None):
        booking = self.get_object()
        driver_id = request.data.get('driver_id')

        if str(booking.driver_id) != str(driver_id):
            return Response({'error': 'Non autorisé'}, status=403)

        booking.status = 'confirmed'
        booking.save()

        try:
            send_booking_event({
                "event": "booking_confirmed",
                "bookingId": booking.id,
                "driverId": booking.driver_id,
                "passengerId": booking.user_id,
                "seats": booking.seats_booked,
                "tripId": booking.trip_id
            })
            print(f"✅ Message envoyé pour confirmation: booking {booking.id}")
        except Exception as e:
            print(f"❌ Erreur envoi confirmation: {e}")

        return Response({'status': 'confirmed', 'booking_id': booking.id})

    @action(detail=True, methods=['post'])
    def complete_trip(self, request, pk=None):
        booking = self.get_object()
        user_id = request.data.get('user_id')
        user_type = request.data.get('user_type')
        
        if user_type == 'passenger' and str(booking.user_id) != str(user_id):
            return Response({'error': 'Non autorisé'}, status=403)
        if user_type == 'driver' and str(booking.driver_id) != str(user_id):
            return Response({'error': 'Non autorisé'}, status=403)
        
        if user_type == 'passenger':
            booking.passenger_confirmed = True
        else:
            booking.driver_confirmed = True
        
        booking.save()
        
        if booking.passenger_confirmed and booking.driver_confirmed:
            booking.status = 'completed'
            booking.completed_at = timezone.now()
            booking.save()
            
            if booking.transaction_id and booking.payment_method != 'cash':
                try:
                    response = requests.post(
                        f"{settings.PAYMENT_SERVICE_URL}/api/payments/release/",
                        json={'transaction_id': str(booking.transaction_id)},
                        timeout=10
                    )
                    if response.status_code == 200:
                        print(f"✅ Paiement libéré pour booking {booking.id}")
                except Exception as e:
                    print(f"⚠️ Erreur libération: {e}")
            
            return Response({'status': 'completed', 'booking_id': booking.id})
        
        return Response({'status': booking.status, 'message': 'Attente confirmation autre partie'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        user_id = request.data.get('user_id')
        reason = request.data.get('reason', 'Annulation')

        if str(booking.user_id) == str(user_id):
            booking.status = 'cancelled_by_passenger'
        elif str(booking.driver_id) == str(user_id):
            booking.status = 'cancelled_by_driver'
        else:
            return Response({'error': 'Non autorisé'}, status=403)

        booking.cancel_reason = reason
        booking.save()

        try:
            send_booking_event({
                "event": booking.status,
                "bookingId": booking.id,
                "userId": user_id,
                "driverId": booking.driver_id,
                "passengerId": booking.user_id,
                "reason": reason,
                "seats": booking.seats_booked
            })
            print(f"✅ Message envoyé pour annulation: {booking.status}")
        except Exception as e:
            print(f"❌ Erreur envoi annulation: {e}")

        if booking.transaction_id and booking.payment_method != 'cash':
            try:
                requests.post(f"{settings.PAYMENT_SERVICE_URL}/api/payments/refund/{booking.transaction_id}/", json={
                    'reason': reason
                })
            except:
                pass

        return Response({'status': booking.status, 'message': 'Annulé avec succès'})


# RATINGS
@api_view(['GET'])
def get_driver_ratings(request, driver_id):
    ratings = Rating.objects.filter(driver_id=driver_id)
    avg_rating = ratings.aggregate(models.Avg('rating'))['rating__avg']
    total_ratings = ratings.count()
    
    distribution = [0, 0, 0, 0, 0]
    for r in ratings:
        if 1 <= r.rating <= 5:
            distribution[r.rating - 1] += 1
    
    return Response({
        'average_rating': round(avg_rating, 1) if avg_rating else None,
        'total_ratings': total_ratings,
        'distribution': distribution,
        'ratings': list(ratings.values('id', 'rating', 'comment', 'created_at', 'passenger_name'))
    })


@api_view(['GET'])
def get_all_ratings(request):
    ratings = Rating.objects.all().order_by('-created_at')[:50]
    return Response(list(ratings.values('id', 'driver_id', 'passenger_id', 'passenger_name', 'rating', 'comment', 'created_at')))


@api_view(['POST'])
def create_rating(request):
    data = request.data
    booking_id = data.get('booking_id')
    driver_id = data.get('driver_id')
    passenger_id = data.get('passenger_id')
    passenger_name = data.get('passenger_name', '')
    rating_val = data.get('rating')
    comment = data.get('comment', '')
    
    if not booking_id or not driver_id or not passenger_id or not rating_val:
        return Response({'error': 'Missing fields'}, status=400)
    
    if rating_val < 1 or rating_val > 5:
        return Response({'error': 'Rating must be between 1 and 5'}, status=400)
    
    try:
        booking = Booking.objects.get(id=booking_id, user_id=passenger_id)
        if booking.status != 'completed':
            return Response({'error': 'Trip not completed yet'}, status=400)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=404)
    
    rating, created = Rating.objects.get_or_create(
        booking_id=booking_id,
        defaults={
            'driver_id': driver_id,
            'passenger_id': passenger_id,
            'passenger_name': passenger_name,
            'rating': rating_val,
            'comment': comment
        }
    )
    
    if not created:
        return Response({'error': 'Rating already exists'}, status=400)
    
    # ✅ AJOUTER ICI LA SYNCHRONISATION
    try:
        import psycopg2
        avg_rating = Rating.objects.filter(driver_id=driver_id).aggregate(models.Avg('rating'))['rating__avg']
        conn = psycopg2.connect(
            host='postgres', database='auth_db',
            user='postgres', password='postgres', port=5432
        )
        cur = conn.cursor()
        cur.execute("UPDATE users_profile SET rating_as_driver = %s WHERE user_id = %s", (avg_rating, driver_id))
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Note conducteur {driver_id} mise à jour: {avg_rating}")
    except Exception as e:
        print(f"⚠️ Erreur synchro note: {e}")
    
    return Response({'status': 'created', 'id': rating.id}, status=201)