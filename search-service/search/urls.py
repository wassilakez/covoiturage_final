from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.SearchRidesView.as_view(), name='search'),
    path('autocomplete/', views.CityAutocompleteView.as_view(), name='autocomplete'),
    path('stats/', views.SearchStatsView.as_view(), name='search-stats'),
]