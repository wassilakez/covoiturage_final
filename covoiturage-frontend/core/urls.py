from django.urls import path
from . import views

urlpatterns = [
    # ── Pages publiques ──────────────────────────────────────────────────────
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),

    # ── Trajets ──────────────────────────────────────────────────────────────
    path('publish/', views.publish_trip, name='publish_trip'),
    path('search/', views.search_trips, name='search_trips'),
    path('trip/<int:trip_id>/', views.trip_detail, name='trip_detail'),

    # ── Réservations ─────────────────────────────────────────────────────────
    path('request/<int:trip_id>/', views.request_booking, name='request_booking'),
    path('booking/<int:booking_id>/confirm/', views.confirm_booking_request, name='confirm_booking'),
    path('booking/<int:booking_id>/complete/', views.complete_trip, name='complete_trip'),
    path('booking/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('booking/<int:booking_id>/refuse/', views.refuse_booking, name='refuse_booking'),
    path('booking/<int:booking_id>/driver-no-show/', views.report_driver_no_show, name='report_driver_no_show'),
    path('booking/<int:booking_id>/passenger-no-show/', views.report_passenger_no_show, name='report_passenger_no_show'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('my-trips/', views.my_bookings, name='my_trips'),

    # ── Évaluations ──────────────────────────────────────────────────────────
    path('rate-driver/<int:booking_id>/', views.rate_driver, name='rate_driver'),

    # ── Admin ─────────────────────────────────────────────────────────────────
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('refund-booking/', views.refund_booking, name='refund_booking'),

    # Actions admin — ces 3 routes étaient présentes dans la vue mais pas dans urls.py
    path('admin/toggle-block/<int:user_id>/', views.admin_toggle_block_user, name='admin_toggle_block'),
    path('admin/change-role/<int:user_id>/', views.admin_change_user_role, name='admin_change_role'),
    path('admin/apply-penalty/', views.admin_apply_penalty, name='admin_apply_penalty'),

    # ── API ───────────────────────────────────────────────────────────────────
    path('api/cities/', views.get_cities, name='get_cities'),
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('api/notifications/create/', views.create_notification, name='create_notification'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]