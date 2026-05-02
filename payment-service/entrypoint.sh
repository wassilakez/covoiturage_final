#!/bin/bash

# entrypoint.sh
# Ce script s'exécute au démarrage du conteneur Docker

echo "========================================="
echo "Payment Service Docker Container"
echo "========================================="
echo ""

# Attendre que PostgreSQL soit prêt
if [ -n "$DB_HOST" ]; then
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    while ! nc -z ${DB_HOST} ${DB_PORT:-5432}; do
        sleep 1
    done
    echo "✅ PostgreSQL is ready"
fi

# Attendre que RabbitMQ soit prêt
if [ -n "$RABBITMQ_HOST" ]; then
    echo "Waiting for RabbitMQ at $RABBITMQ_HOST:$RABBITMQ_PORT..."
    while ! nc -z ${RABBITMQ_HOST} ${RABBITMQ_PORT:-5672}; do
        sleep 1
    done
    echo "✅ RabbitMQ is ready"
fi

echo ""
echo "Running Django migrations..."
python manage.py migrate --noinput

echo ""
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo ""
echo "Starting Gunicorn server..."
echo "Listening on 0.0.0.0:8000"
echo ""

# Démarrer Gunicorn
exec gunicorn payment_project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -