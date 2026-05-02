# # payment_project/celery.py

import os
from celery import Celery

# ⚠️ IMPORTANT : Mettez le bon nom de votre projet !
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payment_project.settings')

app = Celery('payment_project')  # ← Changer ici aussi

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')