import requests
import json
import psycopg2
from datetime import datetime, timezone, timedelta
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from .models import Notification

print("✅ views.py chargé correctement")
User = get_user_model()

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS DB
# ──────────────────────────────────────────────────────────────────────────────

def _get_db_conn(database):
    return psycopg2.connect(
        host='postgres', database=database,
        user='postgres', password='postgres', port=5432
    )


def _fetch_user_names(user_ids):
    """Retourne {user_id: 'Prénom Nom'} depuis auth_db en une seule requête."""
    if not user_ids:
        return {}
    try:
        conn = _get_db_conn('auth_db')
        cur  = conn.cursor()
        cur.execute(
            "SELECT id, first_name, last_name FROM users_user WHERE id = ANY(%s)",
            (list(user_ids),)
        )
        result = {}
        for uid, fn, ln in cur.fetchall():
            result[uid] = f"{fn or ''} {ln or ''}".strip() or f"User {uid}"
        cur.close(); conn.close()
        return result
    except Exception as e:
        print(f"Erreur auth_db _fetch_user_names: {e}")
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# LOGIQUE DE REMBOURSEMENT
# ──────────────────────────────────────────────────────────────────────────────

def compute_refund(booking, cancelled_by='passenger'):
    """
    Calcule le montant à rembourser selon les règles métier :

    Annulation par le PASSAGER :
      - Plus de 24h avant le départ   → remboursement 100 %
      - Moins de 24h avant le départ  → remboursement 50 %
      - Après le départ               → pas de remboursement

    Annulation par le CONDUCTEUR :
      → remboursement 100 % toujours (c'est sa faute)

    Annulation par l'ADMIN :
      → 100 % par défaut (paramètre overridable)

    Retourne un dict :
      {
        'refund_amount': float,
        'refund_pct':    int,        # 0 / 50 / 100
        'reason':        str,
        'label':         str,        # message lisible
      }
    """
    amount     = float(booking.get('amount', 0))
    dep_str    = booking.get('departure_datetime') or booking.get('trip_departure_datetime') or ''

    if cancelled_by == 'driver' or cancelled_by == 'admin':
        return {
            'refund_amount': amount,
            'refund_pct':    100,
            'reason':        f'cancelled_by_{cancelled_by}',
            'label':         f'Remboursement intégral de {amount:.0f} DA',
        }

    # Annulation passager — on calcule le délai
    if dep_str:
        try:
            # Normalise la date : "2025-07-15 08:00:00" ou ISO
            dep_dt = datetime.fromisoformat(dep_str[:19])
            # Rendre aware si nécessaire
            if dep_dt.tzinfo is None:
                dep_dt = dep_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = dep_dt - now

            if delta.total_seconds() > 24 * 3600:
                # Plus de 24h → 100 %
                return {
                    'refund_amount': amount,
                    'refund_pct':    100,
                    'reason':        'passenger_cancelled_early',
                    'label':         f'Remboursement intégral de {amount:.0f} DA (annulation > 24h avant départ)',
                }
            elif delta.total_seconds() > 0:
                # Moins de 24h → 50 %
                half = amount * 0.5
                return {
                    'refund_amount': half,
                    'refund_pct':    50,
                    'reason':        'passenger_cancelled_late',
                    'label':         f'Remboursement de {half:.0f} DA (50 % — annulation < 24h avant départ)',
                }
            else:
                # Départ déjà passé → 0 %
                return {
                    'refund_amount': 0,
                    'refund_pct':    0,
                    'reason':        'passenger_cancelled_after_departure',
                    'label':         'Aucun remboursement (départ déjà passé)',
                }
        except Exception as e:
            print(f"Erreur calcul délai: {e}")

    # Fallback : pas de date → 100 %
    return {
        'refund_amount': amount,
        'refund_pct':    100,
        'reason':        'passenger_cancelled_no_date',
        'label':         f'Remboursement intégral de {amount:.0f} DA',
    }


# ──────────────────────────────────────────────────────────────────────────────
# SERVICES EXTERNES
# ──────────────────────────────────────────────────────────────────────────────

def send_notification(message):
    try:
        import pika
        connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
        channel = connection.channel()
        channel.queue_declare(queue='booking_queue', durable=True)
        channel.basic_publish(exchange='', routing_key='booking_queue', body=json.dumps(message))
        connection.close()
    except Exception as e:
        print(f"Erreur RabbitMQ: {e}")


def release_payment(transaction_id, driver_id, amount):
    try:
        r = requests.post(
            "http://payment-service:8084/api/payments/release/",
            json={"transaction_id": transaction_id}, timeout=5
        )
        return r.json()
    except Exception as e:
        print(f"Erreur release: {e}")
        return {"status": "error"}


def refund_passenger(transaction_id, amount, reason):
    try:
        r = requests.post(
            "http://payment-service:8084/api/payments/refund/",
            json={"transaction_id": transaction_id, "amount": amount, "reason": reason},
            timeout=5
        )
        return r.json()
    except Exception as e:
        print(f"Erreur refund: {e}")
        return {"status": "error"}


def sync_user_to_booking_service(user_id):
    try:
        ur = requests.get(f"http://auth-service:8081/api/auth/users/{user_id}/basic/", timeout=5)
        if ur.status_code == 200:
            d = ur.json()
            requests.post("http://booking-service:8011/api/auth/users/sync/", json={
                'id': user_id, 'username': d.get('username'), 'email': d.get('email'),
                'first_name': d.get('first_name',''), 'last_name': d.get('last_name',''),
                'phone': d.get('phone','')
            }, timeout=5)
    except Exception as e:
        print(f"Erreur sync: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# VUES PUBLIQUES
# ──────────────────────────────────────────────────────────────────────────────

def home(request):
    return render(request, 'index.html')


def register(request):
    wants_json = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    def fail(message, status=400, errors=None):
        if wants_json:
            payload = errors if errors is not None else {'error': message}
            return JsonResponse(payload, status=status)
        messages.error(request, message)
        return render(request, 'register.html')

    if request.method == 'POST':
        password = request.POST.get('password')
        if password != request.POST.get('password_confirm'):
            return fail('Les mots de passe ne correspondent pas')

        user_data = {
            'username': request.POST.get('username'),
            'email':    request.POST.get('email'),
            'password': password, 'password_confirm': password,
            'first_name': request.POST.get('first_name',''),
            'last_name':  request.POST.get('last_name',''),
            'phone':      request.POST.get('phone',''),
            'role':       request.POST.get('role','passenger'),
            'city':       request.POST.get('city',''),
            'bio':        request.POST.get('bio',''),
            'vehicle_brand': request.POST.get('vehicle_brand',''),
            'vehicle_model': request.POST.get('vehicle_model',''),
            'vehicle_year': request.POST.get('vehicle_year') or None,
            'vehicle_color': request.POST.get('vehicle_color',''),
            'vehicle_license_plate': request.POST.get('vehicle_license_plate',''),
            'vehicle_seats': request.POST.get('vehicle_seats') or None,
        }
        try:
            resp = requests.post("http://auth-service:8081/api/auth/register/", json=user_data, timeout=10)
            if resp.status_code == 201:
                user_id = resp.json().get('user', {}).get('id')
                sync_user_to_booking_service(user_id)
                if request.POST.get('role') == 'driver':
                    def parse_int(value, default):
                        try:
                            return int(value)
                        except (TypeError, ValueError):
                            return default

                    requests.post("http://trip-service:8002/api/vehicles/create/", json={
                        'owner_id': user_id,
                        'brand':   request.POST.get('vehicle_brand'),
                        'model':   request.POST.get('vehicle_model'),
                        'year':    parse_int(request.POST.get('vehicle_year'), 2020),
                        'color':   request.POST.get('vehicle_color'),
                        'license_plate': request.POST.get('vehicle_license_plate'),
                        'seats':   parse_int(request.POST.get('vehicle_seats'), 4),
                        'vehicle_type': 'car',
                    }, timeout=5)
                files = {}
                if request.FILES.get('profile_picture'): files['profile_picture'] = request.FILES['profile_picture']
                if request.FILES.get('car_registration'):  files['car_registration']  = request.FILES['car_registration']
                if files:
                    try:
                        requests.post("http://auth-service:8081/api/auth/upload/",
                                      files=files, data={'user_id': user_id}, timeout=10)
                    except Exception as e:
                        print(f"Erreur upload: {e}")
                if wants_json:
                    return JsonResponse({'message': 'Inscription réussie', 'redirect': '/login/'}, status=201)
                messages.success(request, 'Inscription réussie ! Connectez-vous.')
                return redirect('login')
            else:
                try:
                    errors = resp.json()
                except ValueError:
                    errors = {'error': resp.text}
                return fail(f'Erreur: {resp.text}', status=resp.status_code, errors=errors)
        except Exception as e:
            return fail(f'Service indisponible: {e}', status=503)
    return render(request, 'register.html')


@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        try:
            resp = requests.post("http://auth-service:8081/api/auth/login/",
                                 json={'email': request.POST.get('email'),
                                       'password': request.POST.get('password')}, timeout=10)
            if resp.status_code == 200:
                data    = resp.json()
                request.session['access_token'] = data.get('access')
                user_data = data.get('user', {})
                user_id   = user_data.get('id')
                if user_id:
                    br = requests.get(f"http://auth-service:8081/api/auth/users/{user_id}/basic/", timeout=5)
                    if br.status_code == 200:
                        user_data = br.json()
                    vr = requests.get(f"http://trip-service:8002/api/vehicles/?owner_id={user_id}", timeout=5)
                    if vr.status_code == 200 and vr.json():
                        v = vr.json()[0]
                        for k in ('brand','model','year','color','license_plate','seats'):
                            user_data[f'vehicle_{k}'] = v.get(k,'-')
                request.session['user'] = user_data
                messages.success(request, 'Connexion réussie!')
                return redirect('home')
            else:
                messages.error(request, 'Email ou mot de passe incorrect')
        except Exception as e:
            messages.error(request, f'Service indisponible: {e}')
    return render(request, 'login.html')


def logout_view(request):
    request.session.flush()
    messages.success(request, 'Déconnecté')
    return redirect('home')


def profile(request):
    if not request.session.get('access_token'):
        return redirect('login')
    
    user_id = request.session.get('user', {}).get('id')
    if not user_id:
        return redirect('login')
    
    try:
        # Appel direct à l'API auth-service
        resp = requests.get(
            f"http://auth-service:8081/api/auth/users/{user_id}/basic/",
            timeout=5
        )
        if resp.status_code == 200:
            user_data = resp.json()
            # La réponse contient déjà city, bio, rating, etc.
            return render(request, 'profile.html', {'user': user_data})
        else:
            messages.error(request, 'Impossible de charger le profil')
    except Exception as e:
        print(f"Erreur profil: {e}")
        messages.error(request, 'Erreur de connexion')
    
    # Fallback : utiliser les données de session
    return render(request, 'profile.html', {'user': request.session.get('user', {})})


# ──────────────────────────────────────────────────────────────────────────────
# TRAJETS — FIX : lire depuis la DB directement + pas de N+1 HTTP
# ──────────────────────────────────────────────────────────────────────────────

def _get_all_trips_from_db():
    """
    Lit les trajets depuis trip_db + les noms de conducteurs depuis auth_db
    en seulement 2 requêtes SQL (pas de N+1 HTTP).
    Retourne une liste de dicts prêts pour le template.
    """
    trips = []
    try:
        conn = _get_db_conn('trip_db')
        cur  = conn.cursor()
        cur.execute("""
   SELECT t.id, t.driver_id, t.price_per_seat, t.total_seats,
          t.available_seats, t.departure_datetime, t.status,
          t.description,
          c1.name_fr AS dep_name, c2.name_fr AS arr_name
   FROM   trajet_app_ride t
   LEFT JOIN trajet_app_city c1 ON t.departure_city_id = c1.id
   LEFT JOIN trajet_app_city c2 ON t.arrival_city_id = c2.id
   ORDER  BY t.departure_datetime DESC
""")
        rows = cur.fetchall()
        cur.close(); conn.close()

        driver_ids = list({r[1] for r in rows if r[1]})
        names      = _fetch_user_names(driver_ids)

        # Ratings en masse depuis booking_db
        ratings = {}
        try:
            conn2 = _get_db_conn('booking_db')
            cur2  = conn2.cursor()
            cur2.execute("""
                SELECT driver_id,
                       ROUND(AVG(rating)::numeric, 1) AS avg_rating,
                       COUNT(*) AS cnt
                FROM   booking_rating
                GROUP  BY driver_id
            """)
            for did, avg, cnt in cur2.fetchall():
                ratings[did] = {'avg': float(avg), 'cnt': int(cnt)}
            cur2.close(); conn2.close()
        except Exception as e:
            print(f"Erreur ratings: {e}")

        for r in rows:
            did = r[1]
            rating_info = ratings.get(did, {})
            trips.append({
                'id':                 r[0],
                'driver_id':          did,
                'price_per_seat':     float(r[2]) if r[2] else 0,
                'total_seats':        r[3] or 0,
                'available_seats':    r[4] or 0,
                'departure_datetime': str(r[5]) if r[5] else '',
                'status':             r[6] or 'active',
                'description':        r[7] or '',
                'departure_city_name': r[8] or 'Inconnue',
                'arrival_city_name':   r[9] or 'Inconnue',
                'driver_name':         names.get(did, f'Conducteur {did}'),
                'driver_photo':        None,
                'driver_avg_rating':   rating_info.get('avg'),
                'driver_rating_count': rating_info.get('cnt', 0),
            })
    except Exception as e:
        print(f"Erreur _get_all_trips_from_db: {e}")
    return trips


def search_trips(request):
    all_trips = _get_all_trips_from_db()

    filtre_depart   = request.GET.get('departure', '').strip().lower()
    filtre_arrivee  = request.GET.get('destination', '').strip().lower()
    filtre_date     = request.GET.get('date', '')
    filtre_prix_max = request.GET.get('price_max', '')
    filtre_heure    = request.GET.get('time_slot', '')
    filtre_note     = request.GET.get('rating', '')

    prix_max = int(filtre_prix_max) if filtre_prix_max else 999999
    note_min = 4.5 if filtre_note == '4.5' else (4.0 if filtre_note == '4.0' else 0)

    heure_debut, heure_fin = None, None
    if filtre_heure == 'morning':   heure_debut, heure_fin = 0, 12
    elif filtre_heure == 'afternoon': heure_debut, heure_fin = 12, 18
    elif filtre_heure == 'evening':   heure_debut, heure_fin = 18, 24

    trips = []
    for t in all_trips:
        dep_nom = (t['departure_city_name'] or '').lower()
        arr_nom = (t['arrival_city_name']   or '').lower()

        if filtre_depart  and filtre_depart  not in dep_nom: continue
        if filtre_arrivee and filtre_arrivee not in arr_nom: continue

        date_trip = t['departure_datetime'][:10]
        if filtre_date and date_trip != filtre_date: continue

        if t['price_per_seat'] > prix_max: continue

        if filtre_heure and heure_debut is not None:
            dt_str = t['departure_datetime']
            if len(dt_str) >= 13:
                heure = int(dt_str[11:13])
                if not (heure_debut <= heure < heure_fin): continue

        note = t.get('driver_avg_rating') or 0
        if note < note_min: continue

        trips.append(t)

    return render(request, 'search.html', {'trips': trips})


def trip_detail(request, trip_id):
    """
    On lit le trajet depuis la DB pour ne pas dépendre du HTTP trip-service.
    """
    all_trips = _get_all_trips_from_db()
    trip = next((t for t in all_trips if t['id'] == trip_id), None)

    if not trip:
        # Fallback HTTP si pas en DB
        try:
            resp = requests.get(f"http://trip-service:8002/api/trips/{trip_id}/", timeout=10)
            if resp.status_code == 200:
                trip = resp.json()
        except Exception:
            pass

    if not trip:
        messages.error(request, 'Trajet non trouvé')
        return redirect('search_trips')

    # Formate date/heure
    dep_datetime = trip.get('departure_datetime', '')
    if dep_datetime:
        trip['date_only'] = dep_datetime[:10]
        trip['time_only'] = dep_datetime[11:16] if len(dep_datetime) >= 16 else ''
        parts = trip['date_only'].split('-')
        trip['date_fr'] = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else trip['date_only']
    else:
        trip['date_only'] = trip['time_only'] = trip['date_fr'] = ''

    # ✅ AJOUTE CETTE PARTIE POUR RÉCUPÉRER LA PHOTO ET LES INFOS DU CONDUCTEUR
    driver_id = trip.get('driver_id')
    if driver_id:
        try:
            user_resp = requests.get(
                f"http://auth-service:8081/api/auth/users/{driver_id}/basic/",
                timeout=5
            )
            if user_resp.status_code == 200:
                user_data = user_resp.json()
                trip['driver_photo'] = user_data.get('profile_picture')
                trip['driver_name'] = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                trip['driver_avg_rating'] = user_data.get('rating_as_driver')
                trip['driver_rating_count'] = user_data.get('trips_completed')
        except Exception as e:
            print(f"Erreur récupération conducteur: {e}")

    return render(request, 'trip_detail.html', {'trip': trip})


def publish_trip(request):
    if not request.session.get('access_token'):
        return redirect('login')

    if request.method == 'POST':
        dep_id = request.POST.get('departure')
        arr_id = request.POST.get('destination')
        if not dep_id or not arr_id:
            messages.error(request, 'Veuillez sélectionner les villes')
            return render(request, 'publish.html')
        try:
            dep_id = int(dep_id); arr_id = int(arr_id)
        except ValueError:
            messages.error(request, 'Ville invalide')
            return render(request, 'publish.html')

        headers = {'Authorization': f'Bearer {request.session["access_token"]}'}
        try:
            ur = requests.get('http://auth-service:8081/api/auth/profile/', headers=headers, timeout=5)
            if ur.status_code != 200:
                messages.error(request, 'Erreur récupération profil'); return redirect('login')
            driver_id = ur.json().get('user', {}).get('id')
        except Exception as e:
            messages.error(request, f'Erreur: {e}'); return redirect('login')

        if not driver_id:
            messages.error(request, 'Utilisateur non identifié'); return redirect('login')

        departure_datetime = f"{request.POST.get('departure_date')} {request.POST.get('departure_time')}:00"
        trip_data = {
            'departure_city': dep_id, 'arrival_city': arr_id,
            'departure_datetime': departure_datetime,
            'price_per_seat': float(request.POST.get('price_per_seat')),
            'total_seats':    int(request.POST.get('available_seats')),
            'available_seats':int(request.POST.get('available_seats')),
            'vehicle_id': 1, 'driver_id': driver_id,
            'description': request.POST.get('description',''),
        }
        try:
            resp = requests.post("http://trip-service:8002/api/trips/create/",
                                 json=trip_data, headers=headers, timeout=10)
            if resp.status_code == 201:
                send_notification({'type':'trip_published','driver_id':driver_id})
                messages.success(request, 'Trajet publié avec succès!')
                return redirect('search_trips')
            else:
                messages.error(request, f'Erreur: {resp.text}')
        except Exception as e:
            messages.error(request, f'Erreur: {e}')

    return render(request, 'publish.html')


# ──────────────────────────────────────────────────────────────────────────────
# RÉSERVATIONS
# ──────────────────────────────────────────────────────────────────────────────

def request_booking(request, trip_id):
    if not request.session.get('access_token'):
        messages.error(request, 'Connectez-vous pour réserver')
        return redirect('login')
    if request.method != 'POST':
        return redirect('trip_detail', trip_id=trip_id)

    user_id = request.session.get('user', {}).get('id')
    trip_resp = requests.get(f"http://trip-service:8002/api/trips/{trip_id}/")
    if trip_resp.status_code != 200:
        messages.error(request, 'Trajet non trouvé'); return redirect('search_trips')

    trip_data      = trip_resp.json()
    driver_id      = trip_data.get('driver_id')
    price_per_seat = float(trip_data.get('price_per_seat', 0))
    seats          = int(request.POST.get('seats', 1))
    payment_method = request.POST.get('payment_method', 'cash')
     # ========== VALIDATION SELON MODE DE PAIEMENT ==========
    if payment_method == 'cib':
        card_number = request.POST.get('card_number', '')
        expiry = request.POST.get('expiry', '')
        cvv = request.POST.get('cvv', '')
        cardholder = request.POST.get('cardholder', '')
        
        if not card_number or len(card_number.replace(' ', '')) < 15:
            messages.error(request, 'Numéro de carte invalide')
            return redirect('trip_detail', trip_id=trip_id)
        if not expiry or len(expiry) < 5:
            messages.error(request, 'Date d\'expiration invalide')
            return redirect('trip_detail', trip_id=trip_id)
        if not cvv or len(cvv) < 3:
            messages.error(request, 'CVV invalide')
            return redirect('trip_detail', trip_id=trip_id)
        if not cardholder:
            messages.error(request, 'Nom du titulaire requis')
            return redirect('trip_detail', trip_id=trip_id)
            
    elif payment_method == 'ccp':
     ccp_number = request.POST.get('ccp_number', '')
     ccp_key = request.POST.get('ccp_key', '')
     ccp_holder = request.POST.get('ccp_holder', '')
    
     print(f"[CCP] number={ccp_number}, key={ccp_key}, holder={ccp_holder}")
     print(f"[CCP] cleaned_len={len(ccp_number.replace(' ', ''))}")
    
     if not ccp_number or len(ccp_number.replace(' ', '')) < 10:
        messages.error(request, 'Numéro CCP invalide (10 chiffres requis)')
        return redirect('trip_detail', trip_id=trip_id)
     if not ccp_key:
        messages.error(request, 'Clé CCP invalide')
        return redirect('trip_detail', trip_id=trip_id)
     if not ccp_holder:
        messages.error(request, 'Nom du titulaire requis')
        return redirect('trip_detail', trip_id=trip_id)
            
    elif payment_method == 'dahabiya':
        dahabiya_number = request.POST.get('dahabiya_number', '')
        dahabiya_code = request.POST.get('dahabiya_code', '')
        dahabiya_holder = request.POST.get('dahabiya_holder', '')
        
        if not dahabiya_number or len(dahabiya_number.replace(' ', '')) < 15:
            messages.error(request, 'Numéro Dahabiya invalide')
            return redirect('trip_detail', trip_id=trip_id)
        if not dahabiya_code:
            messages.error(request, 'Code secret invalide')
            return redirect('trip_detail', trip_id=trip_id)
        if not dahabiya_holder:
            messages.error(request, 'Nom du titulaire requis')
            return redirect('trip_detail', trip_id=trip_id)
    # ========== FIN VALIDATION ==========
    
   

    amount         = price_per_seat * seats

    booking_data = {
        'user_id': user_id, 'trip_id': trip_id, 'driver_id': driver_id,
        'seats_booked': seats, 'payment_method': payment_method,
        'amount': amount, 'status': 'confirmed' if payment_method != 'cash' else 'pending',
        'departure_datetime': trip_data.get('departure_datetime',''),
    }
    br = requests.post("http://booking-service:8011/api/bookings/", json=booking_data)
    if br.status_code != 201:
        try:    error_msg = br.json().get('error','Erreur inconnue')
        except: error_msg = br.text
        messages.error(request, error_msg)
        return redirect('trip_detail', trip_id=trip_id)

    booking    = br.json()
    booking_id = booking.get('id')
    
    if payment_method != 'cash':
        try:
            pr = requests.post("http://payment-service:8084/api/payments/create/", json={
                'user_id': user_id, 'amount': amount,
                'payment_method': payment_method,
                'booking_id': str(booking_id), 'trip_id': trip_id,
            }, timeout=10)
            if pr.status_code in [200, 201]:
                tid = pr.json().get('transaction_id')
                requests.patch(f"http://booking-service:8011/api/bookings/{booking_id}/",
                               json={'transaction_id': tid})
                messages.success(request, '✅ Réservation confirmée !')
            else:
                messages.warning(request, '⚠️ Réservation créée, paiement en attente')
        except Exception as e:
            messages.warning(request, '⚠️ Réservation créée, problème technique')
    else:
        messages.success(request, '✅ Demande envoyée au conducteur')
    
    return redirect('my_bookings')


def confirm_booking_request(request, booking_id):
    if not request.session.get('access_token'): return redirect('login')
    headers = {'Authorization': f"Bearer {request.session['access_token']}"}
    try:
        br = requests.get(f"http://booking-service:8011/api/bookings/{booking_id}/", headers=headers, timeout=5)
        if br.status_code != 200:
            messages.error(request, 'Réservation non trouvée'); return redirect('my_bookings')
        booking = br.json()
        if booking.get('driver_id') != request.session.get('user',{}).get('id'):
            messages.error(request, "Vous n'êtes pas le conducteur"); return redirect('my_bookings')
        resp = requests.patch(f"http://booking-service:8011/api/bookings/{booking_id}/",
                              json={'status':'confirmed'}, headers=headers, timeout=10)
        if resp.status_code == 200:
            send_notification({'type':'booking_confirmed','booking_id':booking_id})
            messages.success(request, '✅ Réservation confirmée !')
        else:
            messages.error(request, 'Erreur lors de la confirmation')
    except Exception as e:
        messages.error(request, f'Erreur: {e}')
    return redirect('my_bookings')


def refuse_booking(request, booking_id):
    if not request.session.get('access_token'): return redirect('login')
    headers = {'Authorization': f"Bearer {request.session['access_token']}"}
    try:
        resp = requests.patch(f"http://booking-service:8011/api/bookings/{booking_id}/",
                              json={'status':'cancelled'}, headers=headers, timeout=10)
        if resp.status_code == 200:
            send_notification({'type':'booking_refused','booking_id':booking_id})
            messages.success(request, '❌ Réservation refusée')
        else:
            messages.error(request, 'Erreur')
    except Exception as e:
        messages.error(request, f'Erreur: {e}')
    return redirect('my_bookings')


def cancel_booking(request, booking_id):
    """
    Annulation par passager ou conducteur.
    La règle de remboursement est calculée automatiquement par compute_refund().
    """
    if not request.session.get('access_token'): return redirect('login')
    try:
        br = requests.get(f"http://booking-service:8011/api/bookings/{booking_id}/", timeout=5)
        if br.status_code != 200:
            messages.error(request, 'Réservation non trouvée'); return redirect('my_bookings')

        booking  = br.json()
        user_id  = request.session.get('user', {}).get('id')
        driver_id= booking.get('driver_id')

        cancelled_by = 'driver' if user_id == driver_id else 'passenger'
        notif_type   = f'booking_cancelled_by_{cancelled_by}'

        # Paiement non-cash ET déjà confirmée → appliquer la règle de remboursement
        if booking.get('payment_method') != 'cash' and booking.get('status') == 'confirmed':
            refund_info = compute_refund(booking, cancelled_by=cancelled_by)

            if refund_info['refund_pct'] > 0:
                result = refund_passenger(
                    booking.get('transaction_id'),
                    refund_info['refund_amount'],
                    refund_info['reason']
                )
                if result.get('status') != 'error':
                    messages.warning(request, f"💰 {refund_info['label']}")
                else:
                    messages.error(request, 'Erreur lors du remboursement')
            else:
                messages.info(request, refund_info['label'])

        headers = {'Authorization': f"Bearer {request.session['access_token']}"}
        resp = requests.patch(f"http://booking-service:8011/api/bookings/{booking_id}/",
                              json={'status':'cancelled'}, headers=headers, timeout=10)
        if resp.status_code == 200:
            send_notification({'type': notif_type, 'booking_id': booking_id})
            messages.success(request, 'Réservation annulée')
        else:
            messages.error(request, 'Erreur')
    except Exception as e:
        messages.error(request, f'Erreur: {e}')
    return redirect('my_bookings')


def complete_trip(request, booking_id):
    if not request.session.get('access_token'): return redirect('login')
    headers = {'Authorization': f"Bearer {request.session['access_token']}"}
    try:
        br = requests.get(f"http://booking-service:8011/api/bookings/{booking_id}/", headers=headers, timeout=5)
        if br.status_code != 200:
            messages.error(request, 'Réservation non trouvée'); return redirect('my_bookings')
        booking = br.json()
        amount  = float(booking.get('amount', 0))
        if booking.get('payment_method') == 'cash':
            messages.success(request, f'Trajet terminé ! {amount:.0f} DA en espèces.')
        else:
            release_payment(booking.get('transaction_id'), booking.get('driver_id'), amount)
            messages.success(request, f'Trajet terminé ! {amount:.0f} DA débloqués pour le conducteur.')
        requests.patch(f"http://booking-service:8011/api/bookings/{booking_id}/",
                       json={'status':'completed'}, headers=headers, timeout=5)
    except Exception as e:
        messages.error(request, f'Erreur: {e}')
    return redirect('my_bookings')


def report_driver_no_show(request, booking_id):
    if not request.session.get('access_token'): return redirect('login')
    try:
        br = requests.get(f"http://booking-service:8011/api/bookings/{booking_id}/", timeout=5)
        if br.status_code == 200:
            booking = br.json()
            amount  = float(booking.get('amount', 0))
            refund_passenger(booking.get('transaction_id'), amount, "Conducteur absent")
            send_notification({'type':'refund','booking_id':booking_id,'amount':amount})
            messages.success(request, f'Conducteur absent — Remboursement intégral de {amount:.0f} DA')
            headers = {'Authorization': f"Bearer {request.session['access_token']}"}
            requests.patch(f"http://booking-service:8011/api/bookings/{booking_id}/",
                           json={'status':'refunded'}, headers=headers, timeout=5)
        else:
            messages.error(request, 'Réservation non trouvée')
    except Exception as e:
        messages.error(request, f'Erreur: {e}')
    return redirect('my_bookings')


def report_passenger_no_show(request, booking_id):
    if not request.session.get('access_token'): return redirect('login')
    try:
        br = requests.get(f"http://booking-service:8011/api/bookings/{booking_id}/", timeout=5)
        if br.status_code == 200:
            booking     = br.json()
            amount      = float(booking.get('amount', 0))
            compensation= amount * 0.5
            # On rembourse 50% au passager, le conducteur garde 50%
            refund_passenger(booking.get('transaction_id'), compensation, "Passager absent")
            messages.success(request, f'Passager absent — Compensation de {compensation:.0f} DA au conducteur')
            headers = {'Authorization': f"Bearer {request.session['access_token']}"}
            requests.patch(f"http://booking-service:8011/api/bookings/{booking_id}/",
                           json={'status':'completed','compensation':str(compensation)},
                           headers=headers, timeout=5)
        else:
            messages.error(request, 'Réservation non trouvée')
    except Exception as e:
        messages.error(request, f'Erreur: {e}')
    return redirect('my_bookings')


def rate_driver(request, booking_id):
    if not request.session.get('access_token'): return redirect('login')
    if request.method == 'POST':
        rating  = request.POST.get('rating')
        comment = request.POST.get('comment','')
        if not rating or not (1 <= int(rating) <= 5):
            messages.error(request, 'Note invalide (1 à 5)'); return redirect('my_bookings')
        user_id = request.session.get('user',{}).get('id')
        headers = {'Authorization': f"Bearer {request.session['access_token']}"}
        try:
            br = requests.get(f"http://booking-service:8011/api/bookings/{booking_id}/", headers=headers, timeout=5)
            if br.status_code != 200:
                messages.error(request, 'Réservation non trouvée'); return redirect('my_bookings')
            booking   = br.json()
            driver_id = booking.get('driver_id')
            if booking.get('status') != 'completed':
                messages.error(request, "Vous ne pouvez noter qu'un trajet terminé"); return redirect('my_bookings')
            cr = requests.get(f"http://booking-service:8011/api/ratings/?booking_id={booking_id}", headers=headers, timeout=5)
            if cr.status_code == 200 and cr.json():
                messages.warning(request, 'Vous avez déjà noté ce conducteur'); return redirect('my_bookings')
            resp = requests.post("http://booking-service:8011/api/ratings/create/", json={
                'booking_id': int(booking_id), 'driver_id': driver_id,
                'passenger_id': user_id, 'rating': int(rating), 'comment': comment,
            }, headers=headers, timeout=10)
            if resp.status_code == 201:
                send_notification({'type':'new_rating','driver_id':driver_id,'rating':int(rating),'booking_id':booking_id})
                messages.success(request, '⭐ Merci pour votre évaluation !')
            else:
                messages.error(request, f'Erreur: {resp.text}')
        except Exception as e:
            messages.error(request, f'Erreur: {e}')
    return redirect('my_bookings')

def get_trip_name(trip_id):
    try:
        conn = _get_db_conn('trip_db')
        cur = conn.cursor()
        cur.execute("""
            SELECT c1.name_fr, c2.name_fr 
            FROM trajet_app_ride t
            LEFT JOIN trajet_app_city c1 ON t.departure_city_id = c1.id
            LEFT JOIN trajet_app_city c2 ON t.arrival_city_id = c2.id
            WHERE t.id = %s
        """, (trip_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0] and row[1]:
            return f"{row[0]} → {row[1]}"
    except Exception as e:
        print(f"Erreur get_trip_name: {e}")
    return f"Trajet #{trip_id}"
def my_bookings(request):
    if not request.session.get('access_token'): return redirect('login')
    user_id   = request.session.get('user',{}).get('id')
    user_role = request.session.get('user',{}).get('role','passenger')

    all_bookings = []
    try:
        resp = requests.get("http://booking-service:8011/api/bookings/", timeout=10)
        if resp.status_code == 200:
            all_bookings = resp.json()
    except Exception as e:
        print(f"Erreur my_bookings: {e}")

    # Enrichir les noms en une seule requête DB
    all_uid = {b.get('user_id') for b in all_bookings} | {b.get('driver_id') for b in all_bookings}
    names   = _fetch_user_names(all_uid)

    passenger_bookings = []
    driver_requests    = []
    driver_confirmed   = []

    for b in all_bookings:
        b['driver_name']    = names.get(b.get('driver_id'),    f"Conducteur {b.get('driver_id')}")
        b['passenger_name'] = names.get(b.get('user_id'),      f"Passager {b.get('user_id')}")
        b['trip_name'] = get_trip_name(b.get('trip_id'))

        if b.get('user_id') == user_id:
            passenger_bookings.append(b)

        if b.get('driver_id') == user_id:
            if b.get('status') == 'pending':    driver_requests.append(b)
            elif b.get('status') == 'confirmed': driver_confirmed.append(b)

    return render(request, 'my_bookings.html', {
        'passenger_bookings': passenger_bookings,
        'driver_requests':    driver_requests,
        'driver_confirmed':   driver_confirmed,
        'user_role':          user_role,
    })


# ──────────────────────────────────────────────────────────────────────────────
# ADMIN DASHBOARD
# ──────────────────────────────────────────────────────────────────────────────

def admin_dashboard(request):
    if not request.session.get('access_token'): return redirect('login')
    if request.session.get('user',{}).get('role') != 'admin':
        messages.error(request, 'Accès non autorisé'); return redirect('home')

    all_trips    = _get_all_trips_from_db()
    all_users    = []
    all_bookings = []
    drivers_list = []

    # Utilisateurs
    try:
        conn = _get_db_conn('auth_db')
        cur  = conn.cursor()
        cur.execute("SELECT id, first_name, last_name, email, role, is_active FROM users_user")
        for r in cur.fetchall():
            u = {'id':r[0],'first_name':r[1] or '','last_name':r[2] or '',
                 'email':r[3] or '','role':r[4] or 'passenger','is_active': r[5] if r[5] is not None else True}
            all_users.append(u)
            if u['role'] == 'driver': drivers_list.append(u)
        cur.close(); conn.close()
    except Exception as e:
        print(f"Erreur users: {e}")

    # Réservations
    try:
        conn = _get_db_conn('booking_db')
        cur  = conn.cursor()
        cur.execute("SELECT id, user_id, driver_id, amount, status, payment_method, transaction_id FROM booking_booking")
        bk_rows = cur.fetchall()
        cur.close(); conn.close()

        bk_uid = list({r[1] for r in bk_rows} | {r[2] for r in bk_rows})
        bk_names = _fetch_user_names(bk_uid)

        for r in bk_rows:
            all_bookings.append({
                'id': r[0], 'user_id': r[1], 'driver_id': r[2],
                'amount': float(r[3]) if r[3] else 0,
                'status': r[4] or 'pending',
                'payment_method': r[5] or 'cash',
                'transaction_id': r[6],
                'passenger_name': bk_names.get(r[1], f'Passager {r[1]}'),
                'driver_name':    bk_names.get(r[2], f'Conducteur {r[2]}'),
            })
    except Exception as e:
        print(f"Erreur bookings: {e}")

    # Données graphique
    day_counts = [0]*7
    for t in all_trips:
        try:
            dt  = datetime.fromisoformat(t['departure_datetime'][:19])
            day_counts[dt.weekday()] += 1
        except Exception:
            pass

    city_counter = {}
    for t in all_trips:
        c = t.get('departure_city_name')
        if c and c != 'Inconnue':
            city_counter[c] = city_counter.get(c,0)+1
    top_cities = sorted(city_counter.items(), key=lambda x:x[1], reverse=True)[:7]

    chart_data = {
        'allTrips':    all_trips,
        'allUsers':    all_users,
        'allBookings': all_bookings,
        'driversList': drivers_list,
        'tripLabels':  ['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'],
        'tripData':    day_counts,
        'cityLabels':  [c[0] for c in top_cities],
        'cityData':    [c[1] for c in top_cities],
        'confirmed':   sum(1 for b in all_bookings if b['status']=='confirmed'),
        'pending':     sum(1 for b in all_bookings if b['status']=='pending'),
        'cancelled':   sum(1 for b in all_bookings if b['status']=='cancelled'),
    }
    return render(request, 'admin_dashboard.html', {'chart_data': chart_data})


# ──────────────────────────────────────────────────────────────────────────────
# ACTIONS ADMIN
# ──────────────────────────────────────────────────────────────────────────────

def refund_booking(request):
    """
    Remboursement admin :
    - Si reason == 'admin_refund'            → 100 %
    - Si reason == 'passenger_cancelled_late'→ 50 %
    - Sinon compute_refund() avec la date du trajet
    """
    if not request.session.get('access_token'): return redirect('login')
    if request.session.get('user',{}).get('role') != 'admin':
        messages.error(request,'Accès non autorisé'); return redirect('home')

    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        reason     = request.POST.get('reason','admin_refund')
        try:
            br = requests.get(f"http://booking-service:8011/api/bookings/{booking_id}/", timeout=5)
            if br.status_code == 200:
                booking        = br.json()
                payment_method = booking.get('payment_method')
                amount         = float(booking.get('amount',0))
                transaction_id = booking.get('transaction_id')

                if payment_method == 'cash':
                    messages.warning(request,
                        f'Réservation #{booking_id}: paiement en espèces — remboursement manuel requis.')
                else:
                    # Calcul du montant selon la raison
                    if reason == 'passenger_cancelled_late':
                        refund_amount = amount * 0.5
                        refund_reason = 'passenger_cancelled_late'
                    elif reason == 'compute_auto':
                        # L'admin demande un calcul automatique basé sur la date
                        info = compute_refund(booking, cancelled_by='passenger')
                        refund_amount = info['refund_amount']
                        refund_reason = info['reason']
                        messages.info(request, info['label'])
                    else:
                        # admin_refund ou tout autre cas → 100 %
                        refund_amount = amount
                        refund_reason = reason

                    result = refund_passenger(transaction_id, refund_amount, refund_reason)
                    if result.get('status') != 'error':
                        messages.success(request, f'✅ Remboursement de {refund_amount:.0f} DA effectué.')
                        headers = {'Authorization': f"Bearer {request.session['access_token']}"}
                        requests.patch(f"http://booking-service:8011/api/bookings/{booking_id}/",
                                       json={'status':'refunded'}, headers=headers, timeout=5)
                    else:
                        messages.error(request,'Échec du remboursement auprès du service de paiement.')
            else:
                messages.error(request, f'Réservation #{booking_id} non trouvée.')
        except Exception as e:
            messages.error(request, f'Erreur: {e}')
    return redirect('admin_dashboard')


@csrf_exempt
def admin_toggle_block_user(request, user_id):
    if not request.session.get('access_token'):
        return JsonResponse({'status':'error','message':'Non authentifié'}, status=401)
    if request.session.get('user',{}).get('role') != 'admin':
        return JsonResponse({'status':'error','message':'Non autorisé'}, status=403)
    if request.method == 'POST':
        try:
            conn = _get_db_conn('auth_db')
            cur  = conn.cursor()
            cur.execute("SELECT is_active FROM users_user WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                return JsonResponse({'status':'error','message':'Utilisateur non trouvé'}, status=404)
            new_state = not row[0]
            cur.execute("UPDATE users_user SET is_active = %s WHERE id = %s", (new_state, user_id))
            conn.commit(); cur.close(); conn.close()
            return JsonResponse({'status':'ok','message':f"Utilisateur {'débloqué' if new_state else 'bloqué'}",'is_active':new_state})
        except Exception as e:
            return JsonResponse({'status':'error','message':str(e)}, status=500)
    return JsonResponse({'status':'error','message':'Méthode non autorisée'}, status=405)


@csrf_exempt
def admin_change_user_role(request, user_id):
    if not request.session.get('access_token'):
        return JsonResponse({'status':'error','message':'Non authentifié'}, status=401)
    if request.session.get('user',{}).get('role') != 'admin':
        return JsonResponse({'status':'error','message':'Non autorisé'}, status=403)
    if request.method == 'POST':
        try:
            conn = _get_db_conn('auth_db')
            cur  = conn.cursor()
            cur.execute("SELECT role FROM users_user WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                return JsonResponse({'status':'error','message':'Utilisateur non trouvé'}, status=404)
            new_role = 'driver' if row[0] == 'passenger' else 'passenger'
            cur.execute("UPDATE users_user SET role = %s WHERE id = %s", (new_role, user_id))
            conn.commit(); cur.close(); conn.close()
            return JsonResponse({'status':'ok','new_role':new_role,'message':f'Rôle changé en {new_role}'})
        except Exception as e:
            return JsonResponse({'status':'error','message':str(e)}, status=500)
    return JsonResponse({'status':'error','message':'Méthode non autorisée'}, status=405)


@csrf_exempt
def admin_apply_penalty(request):
    if not request.session.get('access_token'):
        return JsonResponse({'status':'error','message':'Non authentifié'}, status=401)
    if request.session.get('user',{}).get('role') != 'admin':
        return JsonResponse({'status':'error','message':'Non autorisé'}, status=403)
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        reason  = request.POST.get('reason','Pénalité administrative')
        try:
            amount = float(request.POST.get('amount',0))
            if amount <= 0: raise ValueError('Montant invalide')
        except ValueError as e:
            return JsonResponse({'status':'error','message':str(e)}, status=400)
        try:
            resp = requests.post("http://payment-service:8084/api/payments/penalty/",
                                 json={'user_id':user_id,'amount':amount,'reason':reason}, timeout=10)
            if resp.status_code in [200,201]:
                return JsonResponse({'status':'ok','message':f'Pénalité de {amount:.0f} DA appliquée'})
            else:
                return JsonResponse({'status':'error','message':resp.json().get('error',resp.text)}, status=400)
        except Exception as e:
            return JsonResponse({'status':'error','message':str(e)}, status=500)
    return redirect('admin_dashboard')


# ──────────────────────────────────────────────────────────────────────────────
# API & NOTIFICATIONS
# ──────────────────────────────────────────────────────────────────────────────

def get_cities(request):
    try:
        resp = requests.get("http://trip-service:8002/api/cities/", timeout=5)
        return JsonResponse(resp.json(), safe=False)
    except Exception:
        return JsonResponse([], safe=False)


def get_notifications(request):
    if not request.session.get('access_token'):
        return JsonResponse({'notifications':[],'unread_count':0})
    user_id = request.session.get('user',{}).get('id')
    if not user_id:
        return JsonResponse({'notifications':[],'unread_count':0})
    try:
        notifs       = Notification.objects.filter(user_id=user_id).order_by('-created_at')[:20]
        unread_count = Notification.objects.filter(user_id=user_id, is_read=False).count()
        data = [{'id':n.id,'title':n.title,'message':n.message,'type':n.type,
                 'is_read':n.is_read,'link':n.link,
                 'created_at':n.created_at.strftime('%d/%m/%Y %H:%M')} for n in notifs]
        return JsonResponse({'notifications':data,'unread_count':unread_count})
    except Exception as e:
        print(f"Erreur get_notifications: {e}")
        return JsonResponse({'notifications':[],'unread_count':0})


def mark_notification_read(request, notification_id):
    if request.session.get('access_token'):
        try:
            n = Notification.objects.get(id=notification_id)
            n.is_read = True; n.save()
        except Exception: pass
    return JsonResponse({'status':'ok'})


def mark_all_notifications_read(request):
    if request.session.get('access_token'):
        user_id = request.session.get('user',{}).get('id')
        if user_id:
            Notification.objects.filter(user_id=user_id, is_read=False).update(is_read=True)
    return JsonResponse({'status':'ok'})


@csrf_exempt
def create_notification(request):
    if request.method == 'POST':
        try:
            d = json.loads(request.body)
            if d.get('user_id'):
                Notification.objects.create(
                    user_id=d['user_id'], title=d.get('title'),
                    message=d.get('message'), type=d.get('type','info'), link=d.get('link')
                )
        except Exception as e:
            print(f"Erreur create_notification: {e}")
    return JsonResponse({'status':'ok'})


def admin_get_user_details(request, user_id):
    return JsonResponse({})

def admin_get_stats_advanced(request):
    return JsonResponse({})

@csrf_exempt
def admin_global_refund(request):
    return redirect('admin_dashboard')
