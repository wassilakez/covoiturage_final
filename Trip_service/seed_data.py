
import os
import django
import random
from datetime import datetime, timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trajet_project.settings')
django.setup()

from trajet_app.models import City, Vehicle, Ride

# ========== 1. LES 58 WILAYAS ==========
def seed_cities():
    cities = [
        (1, "أدرار", "Adrar", "Sud"), (2, "الشلف", "Chlef", "Centre"), (3, "الأغواط", "Laghouat", "Sud"),
        (4, "أم البواقي", "Oum El Bouaghi", "Est"), (5, "باتنة", "Batna", "Est"), (6, "بجاية", "Béjaïa", "Centre"),
        (7, "بسكرة", "Biskra", "Sud"), (8, "بشار", "Béchar", "Sud"), (9, "البليدة", "Blida", "Centre"),
        (10, "البويرة", "Bouira", "Centre"), (11, "تمنراست", "Tamanrasset", "Grand Sud"), (12, "تبسة", "Tébessa", "Est"),
        (13, "تلمسان", "Tlemcen", "Ouest"), (14, "تيارت", "Tiaret", "Centre"), (15, "تيزي وزو", "Tizi Ouzou", "Centre"),
        (16, "الجزائر", "Alger", "Centre"), (17, "الجلفة", "Djelfa", "Sud"), (18, "جيجل", "Jijel", "Est"),
        (19, "سطيف", "Sétif", "Est"), (20, "سعيدة", "Saïda", "Ouest"), (21, "سكيكدة", "Skikda", "Est"),
        (22, "سيدي بلعباس", "Sidi Bel Abbès", "Ouest"), (23, "عنابة", "Annaba", "Est"), (24, "قالمة", "Guelma", "Est"),
        (25, "قسنطينة", "Constantine", "Est"), (26, "المدية", "Médéa", "Centre"), (27, "مستغانم", "Mostaganem", "Ouest"),
        (28, "المسيلة", "M'Sila", "Centre"), (29, "معسكر", "Mascara", "Ouest"), (30, "ورقلة", "Ouargla", "Sud"),
        (31, "وهران", "Oran", "Ouest"), (32, "البيض", "El Bayadh", "Sud"), (33, "إليزي", "Illizi", "Grand Sud"),
        (34, "برج بوعريريج", "Bordj Bou Arreridj", "Est"), (35, "بومرداس", "Boumerdès", "Centre"), (36, "الطارف", "El Tarf", "Est"),
        (37, "تندوف", "Tindouf", "Grand Sud"), (38, "تيسمسيلت", "Tissemsilt", "Centre"), (39, "الوادي", "El Oued", "Sud"),
        (40, "خنشلة", "Khenchela", "Est"), (41, "سوق أهراس", "Souk Ahras", "Est"), (42, "تيبازة", "Tipaza", "Centre"),
        (43, "ميلة", "Mila", "Est"), (44, "عين الدفلى", "Aïn Defla", "Centre"), (45, "النعامة", "Naâma", "Sud"),
        (46, "عين تموشنت", "Aïn Témouchent", "Ouest"), (47, "غرداية", "Ghardaïa", "Sud"), (48, "غليزان", "Relizane", "Ouest"),
        (49, "تيميمون", "Timimoun", "Sud"), (50, "برج باجي مختار", "Bordj Badji Mokhtar", "Grand Sud"),
        (51, "أولاد جلال", "Ouled Djellal", "Sud"), (52, "بني عباس", "Béni Abbès", "Sud"), (53, "عين صالح", "In Salah", "Grand Sud"),
        (54, "عين قزام", "In Guezzam", "Grand Sud"), (55, "تقرت", "Touggourt", "Sud"), (56, "جانت", "Djanet", "Grand Sud"),
        (57, "المغير", "El M'Ghair", "Sud"), (58, "المنيعة", "El Menia", "Sud")
    ]
    
    for num, ar, fr, region in cities:
        city, created = City.objects.get_or_create(
            wilaya_number=num,
            defaults={'name_ar': ar, 'name_fr': fr, 'region': region}
        )
    print(f"✅ {City.objects.count()} cities loaded")

# ========== 2. VEHICULES ==========
def seed_vehicles():
    vehicles = [
        (1, "Renault", "Symbol", "123 ABC 16", 4, "car", "Blanc", 2022),
        (1, "Hyundai", "i10", "456 DEF 31", 4, "car", "Rouge", 2023),
        (1, "Dacia", "Logan", "789 GHI 16", 5, "car", "Gris", 2021),
        (2, "Toyota", "Hiace", "012 JKL 31", 8, "van", "Blanc", 2023),
        (2, "Mercedes", "Vito", "345 MNO 25", 7, "van", "Noir", 2024),
        (3, "Volkswagen", "Golf", "678 PQR 23", 5, "car", "Bleu", 2022),
        (3, "Peugeot", "Partner", "901 STU 19", 5, "van", "Blanc", 2021),
        (4, "Kia", "Sportage", "234 VWX 13", 5, "suv", "Noir", 2023),
        (4, "Ford", "Focus", "567 YZA 42", 5, "car", "Argent", 2022),
        (1, "Renault", "Clio", "890 BCD 09", 4, "car", "Vert", 2023),
    ]
    
    for owner, brand, model, plate, seats, vtype, color, year in vehicles:
        Vehicle.objects.get_or_create(
            license_plate=plate,
            defaults={
                'owner_id': owner, 'brand': brand, 'model': model, 'seats': seats,
                'vehicle_type': vtype, 'color': color, 'year': year, 'is_verified': True
            }
        )
    print(f"✅ {Vehicle.objects.count()} vehicles loaded")

# ========== 3. TRAJETS ==========
def seed_rides():
    # Get cities
    algiers = City.objects.get(wilaya_number=16)
    oran = City.objects.get(wilaya_number=31)
    constantine = City.objects.get(wilaya_number=25)
    annaba = City.objects.get(wilaya_number=23)
    setif = City.objects.get(wilaya_number=19)
    tlemcen = City.objects.get(wilaya_number=13)
    bejaia = City.objects.get(wilaya_number=6)
    blida = City.objects.get(wilaya_number=9)
    tizi = City.objects.get(wilaya_number=15)
    jijel = City.objects.get(wilaya_number=18)
    biskra = City.objects.get(wilaya_number=7)
    ouargla = City.objects.get(wilaya_number=30)
    ghardaia = City.objects.get(wilaya_number=47)
    
    vehicles = list(Vehicle.objects.all())
    if not vehicles:
        print("❌ No vehicles found! Run seed_vehicles first.")
        return
    
    now = timezone.now()
    rides = []
    
    # Popular routes (Algiers → everywhere)
    for city, price, duration in [
        (oran, 1500, 5), (constantine, 1800, 6), (annaba, 2200, 7), (setif, 1400, 4),
        (tlemcen, 2000, 7), (bejaia, 1200, 3), (tizi, 600, 2), (jijel, 1600, 5),
        (biskra, 1800, 6), (ouargla, 2500, 9), (ghardaia, 2800, 10)
    ]:
        for day in [1, 3, 5, 7, 10, 15]:  # multiple days
            rides.append({
                'driver_id': random.choice([1, 2, 3, 4]),
                'vehicle_id': random.choice(vehicles).id,
                'departure_city': algiers,
                'arrival_city': city,
                'departure_datetime': now + timedelta(days=day, hours=random.choice([7, 9, 14, 17, 19])),
                'price_per_seat': price + random.randint(-200, 200),
                'total_seats': random.choice([4, 5, 7, 8]),
                'available_seats': random.randint(1, 8),
                'description': f"Trajet confortable vers {city.name_fr}",
                'status': 'scheduled'
            })
    
    # Return trips (Oran → Algiers)
    for day in [1, 2, 4, 6, 8, 12]:
        rides.append({
            'driver_id': random.choice([1, 2]),
            'vehicle_id': random.choice(vehicles).id,
            'departure_city': oran,
            'arrival_city': algiers,
            'departure_datetime': now + timedelta(days=day, hours=random.choice([8, 10, 15, 18])),
            'price_per_seat': 1400 + random.randint(-200, 200),
            'total_seats': random.choice([4, 5, 7, 8]),
            'available_seats': random.randint(1, 8),
            'description': "Retour vers Alger",
            'status': 'scheduled'
        })
    
    # Weekend trips (Friday to Sunday)
    for city, price in [(bejaia, 1500), (jijel, 1800), (tizi, 800), (blida, 300)]:
        for week in [0, 1, 2]:
            rides.append({
                'driver_id': random.choice([3, 4]),
                'vehicle_id': random.choice(vehicles).id,
                'departure_city': algiers,
                'arrival_city': city,
                'departure_datetime': now + timedelta(days=5 + week*7, hours=8),
                'price_per_seat': price,
                'total_seats': random.choice([4, 5, 7]),
                'available_seats': random.randint(1, 7),
                'description': f"Week-end à {city.name_fr} !",
                'status': 'scheduled'
            })
    
    # Past rides (completed)
    for i in range(20):
        rides.append({
            'driver_id': random.choice([1, 2, 3, 4]),
            'vehicle_id': random.choice(vehicles).id,
            'departure_city': random.choice([algiers, oran, constantine, annaba]),
            'arrival_city': random.choice([algiers, oran, constantine, annaba, setif, tlemcen]),
            'departure_datetime': now - timedelta(days=random.randint(1, 30), hours=random.randint(6, 20)),
            'price_per_seat': random.randint(500, 3000),
            'total_seats': random.choice([4, 5, 7, 8]),
            'available_seats': 0,
            'description': "Trajet terminé",
            'status': random.choice(['completed', 'cancelled'])
        })
    
    for ride_data in rides:
        Ride.objects.create(**ride_data)
    
    print(f"✅ {Ride.objects.count()} rides loaded")
    print(f"   - Scheduled: {Ride.objects.filter(status='scheduled').count()}")
    print(f"   - Completed: {Ride.objects.filter(status='completed').count()}")
    print(f"   - Cancelled: {Ride.objects.filter(status='cancelled').count()}")

# ========== RUN ==========
if __name__ == "__main__":
    print("🌱 Seeding database...")
    seed_cities()
    seed_vehicles()
    seed_rides()
    print("\n🎉 Database seeding complete!")