from django.urls import path
from . import views
from .views import UploadView  # Ajoutez cette ligne


urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='api_register'),
    path('login/', views.LoginView.as_view(), name='api_login'),
    path('logout/', views.LogoutView.as_view(), name='api_logout'),
    path('profile/', views.ProfileView.as_view(), name='api_profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='api_change_password'),
    path('sessions/', views.MySessionsView.as_view(), name='api_sessions'),
    path('health/', views.HealthCheckView.as_view(), name='api_health'),
    path('users/<int:user_id>/permissions/', views.UserPermissionsView.as_view(), name='api_user_permissions'),
    path('users/<int:user_id>/basic/', views.UserBasicInfoView.as_view(), name='api_user_basic'),
    path('upload/', UploadView.as_view(), name='upload'),  # Maintenant ça fonctionne
]