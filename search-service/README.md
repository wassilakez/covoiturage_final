# Search Service - Microservice de Recherche Intelligente 🔍

## Description
Service de recherche intelligent pour la plateforme de covoiturage. Permet de rechercher des trajets avec plusieurs filtres et options de tri.

## Technologies
- Django 5.2
- Django REST Framework
- PostgreSQL
- Docker

## Endpoints

### 1. Recherche de trajets
**GET** `/api/search/`

| Paramètre | Type | Description |
|-----------|------|-------------|
| departure | string | Ville de départ (français/arabe/numéro wilaya) |
| arrival | string | Ville d'arrivée |
| date | date | Date spécifique (YYYY-MM-DD) |
| date_type | string | today, tomorrow, week |
| time_of_day | string | morning, afternoon, evening, night |
| min_price | number | Prix minimum |
| max_price | number | Prix maximum |
| passengers | number | Nombre de passagers |
| smoking | string | allowed, not_allowed |
| gender | string | male, female |
| sort | string | price, departure_time, seats |
| order | string | asc, desc |
| page | number | Numéro de page |
| page_size | number | Taille de page |

**Exemples:**
```bash
# Recherche simple
GET /api/search/?departure=Alger&arrival=Oran

# Recherche avec prix
GET /api/search/?departure=Alger&min_price=1000&max_price=2000

# Recherche aujourd'hui
GET /api/search/?date_type=today

# Recherche avec tri
GET /api/search/?departure=Alger&sort=price&order=asc


# Recherche par nombre de passagers
GET /api/search/?passengers=3

# Recherche avec filtres de préférence
GET /api/search/?smoking=not_allowed&gender=female

# Pagination
GET /api/search/?page=2&page_size=10