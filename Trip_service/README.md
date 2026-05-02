# Trip Service 

Microservice de gestion des trajets pour la plateforme de covoiturage.

##  Table des matières
- [Description](#description)
- [Technologies](#technologies)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Docker](#docker)
- [Tests](#tests)
- [Structure du projet](#structure-du-projet)

---

## Description

Ce microservice est responsable de la gestion complète des trajets (CRUD) pour la plateforme de covoiturage. Il permet aux conducteurs de :
- Publier des trajets
- Modifier leurs trajets
- Annuler leurs trajets
- Consulter leurs statistiques

Il gère également :
- Les véhicules des conducteurs
- Les villes algériennes
- Les arrêts intermédiaires (stopovers)

---

##  Technologies

| Technologie | Version | Utilisation |
|-------------|---------|-------------|
| Python | 3.11 | Langage principal |
| Django | 4.2 | Framework web |
| Django REST Framework | 3.14 | API REST |
| PostgreSQL | 15 | Base de données |
| Docker | Latest | Conteneurisation |
| Gunicorn | 21.2 | Serveur WSGI |

---

##  Installation

### Prérequis
- Python 3.11+
- PostgreSQL 15+
- Docker  

### Installation locale

```bash
# 1. Cloner le dépôt
git clone https://github.com/votre-org/covoiturage.git
cd covoiturage/trip-service

# 2. Créer un environnement virtuel
python -m venv venv
 
venv\Scripts\activate     # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer la base de données
# Créer une base PostgreSQL nommée "trajet_db"

# 5. Appliquer les migrations
python manage.py migrate

# 6. Ajouter des données de test
python manage.py shell < seed_data.py

# 7. Lancer le serveur
python manage.py runserver 8002


## 📡 API Endpoints

### Base URL
- **Local development**: `http://localhost:8002`
- **Docker**: `http://localhost:8002`

### Health Check
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health/` | Vérifier que le service fonctionne |

### Cities
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cities/` | Liste de toutes les villes |
| GET | `/api/cities/{id}/` | Détails d'une ville |

### Vehicles
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/vehicles/` | Liste de mes véhicules |
| POST | `/api/vehicles/create/` | Ajouter un véhicule |
| GET | `/api/vehicles/{id}/` | Détails d'un véhicule |
| PUT | `/api/vehicles/{id}/update/` | Modifier un véhicule |
| DELETE | `/api/vehicles/{id}/delete/` | Supprimer un véhicule |

### Rides / Trips
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trips/` | Liste des trajets à venir |
| GET | `/api/all-rides/` | Tous les trajets (passés, présents) |
| GET | `/api/upcoming-rides/` | Trajets à venir |
| GET | `/api/past-rides/` | Trajets passés |
| GET | `/api/trips/{id}/` | Détails d'un trajet |
| POST | `/api/trips/create/` | Créer un nouveau trajet (conducteur) |
| PUT | `/api/trips/{id}/update/` | Modifier un trajet (conducteur) |
| DELETE | `/api/trips/{id}/delete/` | Supprimer un trajet (conducteur) |
| POST | `/api/trips/{id}/cancel/` | Annuler un trajet |
| GET | `/api/my-trips/` | Mes trajets (conducteur) |
| GET | `/api/rides/driver/{driver_id}/` | Trajets d'un conducteur spécifique |

### Stopovers
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/rides/{ride_id}/stopovers/` | Liste des arrêts d'un trajet |
| POST | `/api/rides/{ride_id}/stopovers/create/` | Ajouter un arrêt |
| DELETE | `/api/stopovers/{id}/delete/` | Supprimer un arrêt |

### Statistics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/driver/stats/` | Statistiques du conducteur (nombre de trajets, revenus, passagers) |

### 🔑 Endpoints importants pour Booking Service

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trips/{id}/` | Vérifier les détails d'un trajet (prix, places disponibles) |
| PUT | `/api/trips/{id}/update/` | Mettre à jour les places disponibles après réservation |

---

## Exemples de requêtes

### Créer un trajet
```bash
POST http://localhost:8002/api/trips/create/
Content-Type: application/json

{
    "departure_city": 1,
    "arrival_city": 2,
    "departure_datetime": "2026-04-20T10:00:00",
    "price_per_seat": 1200,
    "total_seats": 4,
    "available_seats": 4,
    "vehicle_id": 1
}