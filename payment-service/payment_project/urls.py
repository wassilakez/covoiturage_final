from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def home(request):
    return HttpResponse("""...""")  # Votre HTML ici

urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),
    path('api/payments/', include('payments.urls')),
]