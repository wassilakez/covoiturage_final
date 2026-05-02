import pika
import json
import requests
import time
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

RABBITMQ_HOST = 'rabbitmq'

# ==================== CONFIGURATION EMAIL ====================
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USER = 'imenaouicha226@gmail.com'
EMAIL_PASSWORD = 'rbuw wdhj onwi uprj'
EMAIL_FROM = 'noreply@covoiturage.com'
EMAIL_TEST_MODE = False

# ==================== FONCTIONS EMAIL ====================
def send_real_email(to_email, subject, body):
    if not to_email:
        return False
    
    if EMAIL_TEST_MODE:
        print(f"📧 [TEST] Email à {to_email}: {subject}")
        return True
    
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email envoyé à {to_email}")
        return True
    except Exception as e:
        print(f"❌ Erreur email: {e}")
        return False

# ==================== FONCTIONS UTILITAIRES ====================
def get_user_info(user_id):
    try:
        response = requests.get(f"http://auth-service:8081/api/auth/users/{user_id}/basic/", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def get_user_email(user_id):
    user = get_user_info(user_id)
    return user.get('email') if user else None

def get_user_name(user_id):
    user = get_user_info(user_id)
    if user:
        first = user.get('first_name', '')
        last = user.get('last_name', '')
        if first or last:
            return f"{first} {last}".strip()
        username = user.get('username', '')
        if username:
            return username
    return f"Utilisateur {user_id}"

def get_booking(booking_id):
    try:
        r = requests.get(f"http://booking-service:8011/api/bookings/{booking_id}/", timeout=5)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def get_trip(trip_id):
    try:
        r = requests.get(f"http://trip-service:8002/api/trips/{trip_id}/", timeout=5)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def create_notification(user_id, title, message, type_val='info', link=None):
    try:
        r = requests.post(
            "http://frontend:8000/api/notifications/create/",
            json={'user_id': user_id, 'title': title, 'message': message, 'type': type_val, 'link': link},
            timeout=5
        )
        print(f"🔔 Notification à user {user_id}: {title}")
        return r.status_code == 200
    except:
        return False

def apply_penalty(driver_id, amount, reason):
    try:
        amount = float(amount) if isinstance(amount, str) else amount
        r = requests.post(
            "http://payment-service:8000/api/payments/penalty/",
            json={'driver_id': driver_id, 'amount': amount, 'reason': reason},
            timeout=5
        )
        if r.status_code == 200:
            create_notification(driver_id, "⚠️ Pénalité", f"Pénalité de {amount} DA - Raison: {reason}", 'penalty', '/profile/')
            return True
    except Exception as e:
        print(f"❌ Erreur pénalité: {e}")
    return False

# ==================== TRAITEMENT DES MESSAGES ====================
def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        # Support pour 'type' et 'event'
        msg_type = data.get('type') or data.get('event')
        print(f"\n{'='*50}\n📨 {msg_type}\n{'='*50}")

        # ---------- 1. NOUVELLE DEMANDE DE RESERVATION ----------
        if msg_type == 'new_booking_request':
            driver_id = data.get('driver_id')
            passenger_id = data.get('passenger_id')
            seats = data.get('seats')
            trip_id = data.get('trip_id')
            booking_id = data.get('booking_id')
            
            passenger_name = get_user_name(passenger_id)
            trip = get_trip(trip_id)
            trip_name = f"{trip.get('departure_city_name', 'Départ')} → {trip.get('arrival_city_name', 'Arrivée')}" if trip else "ton trajet"
            
            create_notification(driver_id, "🚗 Nouvelle demande", f"{passenger_name} veut {seats} place(s) pour {trip_name}", 'booking_request', '/my-bookings/#driver-requests')
            driver_email = get_user_email(driver_id)
            if driver_email:
                send_real_email(driver_email, "🚗 Nouvelle demande de covoiturage", f"""
                <h2>Nouvelle demande</h2>
                <p>{passenger_name} veut réserver {seats} place(s) pour {trip_name}.</p>
                <p><a href='http://localhost:8000/my-bookings/'>Cliquez ici</a> pour répondre.</p>
                """)
            
            create_notification(passenger_id, "📝 Demande envoyée", f"Ta demande pour {seats} place(s) a été envoyée au conducteur", 'info', '/my-bookings/')
            passenger_email = get_user_email(passenger_id)
            if passenger_email:
                send_real_email(passenger_email, "📝 Demande envoyée", f"""
                <h2>Demande envoyée</h2>
                <p>Ta demande pour {seats} place(s) a été envoyée. Tu recevras une réponse bientôt.</p>
                <p><a href='http://localhost:8000/my-bookings/'>Suivre ma demande</a></p>
                """)

        # ---------- 2. RESERVATION CONFIRMEE ----------
        elif msg_type == 'booking_confirmed':
            booking_id = data.get('booking_id')
            booking = get_booking(booking_id)
            if booking:
                passenger_id = booking.get('user_id')
                driver_id = booking.get('driver_id')
                trip_id = booking.get('trip_id')
                seats = booking.get('seats_booked')
                amount = booking.get('amount', 0)
                
                driver_name = get_user_name(driver_id)
                passenger_name = get_user_name(passenger_id)
                trip = get_trip(trip_id)
                trip_name = f"{trip.get('departure_city_name', 'Départ')} → {trip.get('arrival_city_name', 'Arrivée')}" if trip else "ton trajet"
                
                create_notification(passenger_id, "✅ Réservation confirmée", f"{driver_name} a confirmé ta réservation de {seats} place(s) pour {trip_name}", 'booking_confirmed', f'/trip/{trip_id}/')
                passenger_email = get_user_email(passenger_id)
                if passenger_email:
                    send_real_email(passenger_email, "✅ Réservation confirmée - Bon voyage !", f"""
                    <h2>✅ Réservation confirmée !</h2>
                    <p>{driver_name} a confirmé ta réservation de {seats} place(s).</p>
                    <p>Montant: {amount} DA</p>
                    <p>Trajet: {trip_name}</p>
                    <p><a href='http://localhost:8000/trip/{trip_id}/'>Voir le trajet</a></p>
                    """)
                
                create_notification(driver_id, "✅ Réservation confirmée", f"Tu as confirmé la réservation de {seats} place(s) pour {passenger_name}", 'booking_confirmed', '/my-bookings/')

        # ---------- 3. RESERVATION REFUSEE ----------
        elif msg_type == 'booking_refused':
            booking_id = data.get('booking_id')
            booking = get_booking(booking_id)
            if booking:
                passenger_id = booking.get('user_id')
                driver_id = booking.get('driver_id')
                driver_name = get_user_name(driver_id)
                
                create_notification(passenger_id, "❌ Réservation refusée", f"{driver_name} a refusé ta demande", 'booking_cancelled', '/search/')
                passenger_email = get_user_email(passenger_id)
                if passenger_email:
                    send_real_email(passenger_email, "❌ Réservation refusée", f"""
                    <h2>Réservation refusée</h2>
                    <p>{driver_name} a refusé ta demande.</p>
                    <p><a href='http://localhost:8000/search/'>Rechercher d'autres trajets</a></p>
                    """)

        # ---------- 4. ANNULATION PAR CONDUCTEUR ----------
        elif msg_type == 'booking_cancelled_by_driver':
            booking_id = data.get('booking_id')
            booking = get_booking(booking_id)
            if booking:
                passenger_id = booking.get('user_id')
                driver_id = booking.get('driver_id')
                amount = booking.get('amount', 0)
                
                create_notification(passenger_id, "⚠️ Annulé par conducteur", f"Le conducteur a annulé - Remboursement de {amount} DA", 'booking_cancelled', '/my-bookings/')
                passenger_email = get_user_email(passenger_id)
                if passenger_email:
                    send_real_email(passenger_email, "⚠️ Réservation annulée - Remboursement", f"""
                    <h2>Réservation annulée par le conducteur</h2>
                    <p>Un remboursement de {amount} DA va être effectué.</p>
                    <p><a href='http://localhost:8000/search/'>Rechercher un autre trajet</a></p>
                    """)
                
                apply_penalty(driver_id, amount * 0.2, "Annulation de réservation confirmée")

        # ---------- 5. ANNULATION PAR PASSAGER ----------
        elif msg_type == 'booking_cancelled_by_passenger':
            booking_id = data.get('booking_id')
            booking = get_booking(booking_id)
            if booking:
                driver_id = booking.get('driver_id')
                passenger_id = booking.get('user_id')
                seats = booking.get('seats_booked')
                passenger_name = get_user_name(passenger_id)
                
                create_notification(driver_id, "⚠️ Annulé par passager", f"{passenger_name} a annulé sa réservation de {seats} place(s)", 'booking_cancelled', '/my-trips/')
                driver_email = get_user_email(driver_id)
                if driver_email:
                    send_real_email(driver_email, "⚠️ Réservation annulée", f"""
                    <h2>Réservation annulée par le passager</h2>
                    <p>{passenger_name} a annulé sa réservation de {seats} place(s).</p>
                    <p>Les places sont maintenant disponibles.</p>
                    <p><a href='http://localhost:8000/my-trips/'>Voir mes trajets</a></p>
                    """)

        # ---------- 6. NOUVELLE EVALUATION ----------
        elif msg_type == 'new_rating':
            driver_id = data.get('driver_id')
            rating = data.get('rating')
            
            create_notification(driver_id, "⭐ Nouvelle évaluation", f"Tu as reçu une note de {rating}/5", 'info', '/profile/#ratings')
            driver_email = get_user_email(driver_id)
            if driver_email:
                send_real_email(driver_email, "⭐ Nouvelle évaluation", f"""
                <h2>Nouvelle évaluation</h2>
                <p>Tu as reçu une note de {rating}/5.</p>
                <p><a href='http://localhost:8000/profile/'>Voir mon profil</a></p>
                """)

        # ---------- 7. REMBOURSEMENT ----------
        elif msg_type == 'refund':
            booking_id = data.get('booking_id')
            amount = data.get('amount')
            booking = get_booking(booking_id)
            if booking:
                passenger_id = booking.get('user_id')
                
                create_notification(passenger_id, "💰 Remboursement", f"Remboursement de {amount} DA effectué", 'refund', '/my-bookings/')
                passenger_email = get_user_email(passenger_id)
                if passenger_email:
                    send_real_email(passenger_email, "💰 Remboursement effectué", f"""
                    <h2>Remboursement effectué</h2>
                    <p>Un remboursement de {amount} DA a été effectué.</p>
                    <p><a href='http://localhost:8000/my-bookings/'>Voir mes réservations</a></p>
                    """)

        # ---------- 8. TRAJET PUBLIE ----------
        elif msg_type == 'trip_published':
            driver_id = data.get('driver_id')
            
            create_notification(driver_id, "🚀 Trajet publié", "Ton trajet a été publié avec succès !", 'info', '/my-trips/')
            driver_email = get_user_email(driver_id)
            if driver_email:
                send_real_email(driver_email, "🚀 Trajet publié", """
                <h2>Trajet publié !</h2>
                <p>Ton trajet a été publié. Les passagers peuvent maintenant réserver.</p>
                <p><a href='http://localhost:8000/my-trips/'>Voir mes trajets</a></p>
                """)

        # ---------- 9. PENALITE (ADMIN) ----------
        elif msg_type == 'admin_penalty':
            driver_id = data.get('driver_id')
            amount = data.get('amount')
            reason = data.get('reason')
            
            create_notification(driver_id, "⚠️ Pénalité administrative", f"L'admin t'a appliqué une pénalité de {amount} DA - {reason}", 'penalty', '/profile/')
            driver_email = get_user_email(driver_id)
            if driver_email:
                send_real_email(driver_email, "⚠️ Pénalité appliquée", f"""
                <h2>Pénalité appliquée par l'administrateur</h2>
                <p>Montant: {amount} DA</p>
                <p>Raison: {reason}</p>
                <p><a href='http://localhost:8000/contact/'>Contacter le support</a></p>
                """)

        # ---------- 10. REMBOURSEMENT ADMIN ----------
        elif msg_type == 'admin_refund':
            user_id = data.get('user_id')
            amount = data.get('amount')
            reason = data.get('reason')
            
            create_notification(user_id, "💰 Remboursement admin", f"L'admin a effectué un remboursement de {amount} DA - {reason}", 'refund', '/my-bookings/')
            user_email = get_user_email(user_id)
            if user_email:
                send_real_email(user_email, "💰 Remboursement effectué par l'admin", f"""
                <h2>Remboursement effectué par l'administrateur</h2>
                <p>Montant: {amount} DA</p>
                <p>Raison: {reason}</p>
                """)

        # ---------- 11. BLOCAGE CONDUCTEUR (ADMIN) ----------
        elif msg_type == 'admin_block_driver':
            driver_id = data.get('driver_id')
            reason = data.get('reason')
            
            create_notification(driver_id, "🚫 Compte bloqué", f"L'admin a bloqué ton compte - Raison: {reason}", 'penalty', '/contact/')
            driver_email = get_user_email(driver_id)
            if driver_email:
                send_real_email(driver_email, "🚫 Compte bloqué", f"""
                <h2>Votre compte a été bloqué</h2>
                <p>Raison: {reason}</p>
                <p><a href='http://localhost:8000/contact/'>Contacter le support</a></p>
                """)

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"✅ {msg_type} traité\n")

    except Exception as e:
        print(f"❌ Erreur: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

# ==================== DEMARRAGE - ÉCOUTE MULTIPLES QUEUES ====================
def start_consuming():
    retry = 0
    print("="*50)
    print("🚀 CONSUMER NOTIFICATIONS")
    print(f"📧 Mode: {'TEST' if EMAIL_TEST_MODE else 'REEL'}")
    print("="*50)
    
    while retry < 10:
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600))
            channel = conn.channel()
            
            # Déclarer TOUTES les queues
            channel.queue_declare(queue='booking_queue', durable=True)
            channel.queue_declare(queue='payment_queue', durable=True)
            channel.queue_declare(queue='notifications', durable=True)
            
            channel.basic_qos(prefetch_count=1)
            
            # Écouter TOUTES les queues
            channel.basic_consume(queue='booking_queue', on_message_callback=callback, auto_ack=False)
            channel.basic_consume(queue='payment_queue', on_message_callback=callback, auto_ack=False)
            channel.basic_consume(queue='notifications', on_message_callback=callback, auto_ack=False)
            
            print("✅ Connecté à RabbitMQ")
            print("📡 Écoute sur: booking_queue, payment_queue, notifications")
            print("⏳ En attente de messages...\n")
            channel.start_consuming()
            
        except Exception as e:
            print(f"❌ Erreur connexion: {e}")
            retry += 1
            time.sleep(5)
    
    print("❌ Impossible de se connecter")

if __name__ == '__main__':
    start_consuming()