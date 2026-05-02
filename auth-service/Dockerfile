FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ⚠️ AJOUTE CETTE LIGNE POUR COPIER TES TEMPLATES
COPY templates /app/templates/

EXPOSE 8081

CMD ["python", "manage.py", "runserver", "0.0.0.0:8081"]