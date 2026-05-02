# 💰 Payment Service - Plateforme de Covoiturage

## 📋 Description
Service de paiement pour la plateforme de covoiturage intelligent et réservation de transports inter-villes en Algérie.

**Membre 4 - Projet WAMS 2025**

---

## 📡 Informations de connexion

| Information | Valeur |
|-------------|--------|
| **IP** | `172.29.128.1` |
| **Port** | `8000` |
| **Base URL** | `http://172.29.128.1:8000/api/payments/` |

### Test rapide
```bash
curl http://172.29.128.1:8000/api/payments/health/
## 🔗 Endpoints API



| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health/` | Health check |
| GET | `/wallet/` | Voir portefeuille |
| POST | `/wallet/add-balance/` | Recharger (`{"amount": 5000}`) |
| POST | `/create/` | Créer paiement |
| POST | `/confirm/` | Confirmer paiement |
| GET | `/transactions/` | Historique |



🚀 Fonctionnalités
✅ API REST complète pour la gestion des paiements

✅ Portefeuille virtuel utilisateur

✅ Commission plateforme (10%)

✅ Génération de reçus PDF

✅ Communication asynchrone via RabbitMQ

✅ Tâches asynchrones avec Celery

✅ Containerisation Docker

🛠 Technologies utilisées
Technologie	Version
Django	4.2
Django REST Framework	3.14
PostgreSQL	15
RabbitMQ	3.12
Celery	5.3
Docker	Latest
ReportLab	4.0
📋 Endpoints API
Base URL : http://172.29.128.1:8000/api/payments/
Méthode	Endpoint	Description	Body (si POST)
GET	/health/	Vérifier l'état du service	-
GET	/wallet/	Consulter le solde du portefeuille	-
POST	/wallet/add-balance/	Recharger le portefeuille	{"amount": 5000}
POST	/create/	Créer un nouveau paiement	Voir exemple
POST	/confirm/	Confirmer un paiement	{"transaction_id": "uuid"}
GET	/transactions/	Historique des transactions	-
GET	/transactions/{id}/	Détails d'une transaction	-
GET	/transactions/{id}/receipt/	Télécharger le reçu PDF	-
POST	/transactions/{id}/refund/	Demander un remboursement	{"reason": "Annulation"}
📝 Exemples d'utilisation
1. Health Check
bash
curl http://172.29.128.1:8000/api/payments/health/
2. Voir le portefeuille
bash
curl http://172.29.128.1:8000/api/payments/wallet/
3. Ajouter du solde
bash
curl -X POST http://172.29.128.1:8000/api/payments/wallet/add-balance/ \
  -H "Content-Type: application/json" \
  -d '{"amount": 10000}'
4. Créer un paiement
bash
curl -X POST http://172.29.128.1:8000/api/payments/create/ \
  -H "Content-Type: application/json" \
  -d '{
    "booking_id": "123e4567-e89b-12d3-a456-426614174000",
    "amount": 1500,
    "payment_method": "cash",
    "metadata": {
        "from_city": "Alger",
        "to_city": "Oran"
    }
}'
5. Confirmer un paiement
bash
curl -X POST http://172.29.128.1:8000/api/payments/confirm/ \
  -H "Content-Type: application/json" \
  -d '{"transaction_id": "550e8400-e29b-41d4-a716-446655440000"}'
6. Voir l'historique
bash
curl http://172.29.128.1:8000/api/payments/transactions/
7. Télécharger un reçu PDF
text
http://172.29.128.1:8000/api/payments/transactions/550e8400-e29b-41d4-a716-446655440000/receipt/
🎯 Méthodes de paiement
Code	Moyen	Description
cash	Espèces	Paiement en espèces au chauffeur
cib	Carte bancaire	Paiement par carte bancaire
edahabia	Edahabia	Paiement via Edahabia
ccp	CCP	Paiement par virement CCP
wallet	Portefeuille	Paiement via portefeuille virtuel
📊 Statuts des transactions
Statut	Signification
pending	⏳ En attente de confirmation
processing	🔄 En cours de traitement
completed	✅ Paiement confirmé
failed	❌ Échec du paiement
refunded	🔁 Remboursé
