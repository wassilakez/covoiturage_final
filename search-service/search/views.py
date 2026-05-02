from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Ride, City
from django.db import models

class SearchRidesView(APIView):
    """
    Intelligent Search with multiple filters:
    - Search by city (French, Arabic, wilaya number, partial match)
    - Search by date (specific date, today, tomorrow, this week)
    - Search by time of day (morning, afternoon, evening, night)
    - Search by price range
    - Search by available seats
    - Search by preferences (smoking, gender)
    - Sort options (price, time, seats)
    - Pagination
    """
    permission_classes = []
    
    def get(self, request):
        # Base query: only active scheduled rides in the future
        rides = Ride.objects.filter(
            status='scheduled',
            departure_datetime__gt=timezone.now()
        ).select_related('departure_city', 'arrival_city')
        
        # ========== 1. SEARCH BY CITY (Intelligent) ==========
        departure = request.query_params.get('departure', '')
        arrival = request.query_params.get('arrival', '')
        
        if departure:
            rides = rides.filter(
                Q(departure_city__name_fr__icontains=departure) |
                Q(departure_city__name_ar__icontains=departure) |
                Q(departure_city__wilaya_number__icontains=departure)
            )
        
        if arrival:
            rides = rides.filter(
                Q(arrival_city__name_fr__icontains=arrival) |
                Q(arrival_city__name_ar__icontains=arrival) |
                Q(arrival_city__wilaya_number__icontains=arrival)
            )
        
        # ========== 2. SEARCH BY DATE ==========
        date = request.query_params.get('date', '')
        date_type = request.query_params.get('date_type', '')
        
        if date_type == 'today':
            today = timezone.now().date()
            rides = rides.filter(departure_datetime__date=today)
        elif date_type == 'tomorrow':
            tomorrow = timezone.now().date() + timedelta(days=1)
            rides = rides.filter(departure_datetime__date=tomorrow)
        elif date_type == 'week':
            next_week = timezone.now().date() + timedelta(days=7)
            rides = rides.filter(departure_datetime__date__lte=next_week)
        elif date:
            try:
                search_date = datetime.strptime(date, '%Y-%m-%d').date()
                rides = rides.filter(departure_datetime__date=search_date)
            except ValueError:
                pass
        
        # ========== 3. SEARCH BY TIME OF DAY ==========
        time_of_day = request.query_params.get('time_of_day', '')
        if time_of_day == 'morning':
            rides = rides.filter(departure_datetime__hour__gte=6, departure_datetime__hour__lt=12)
        elif time_of_day == 'afternoon':
            rides = rides.filter(departure_datetime__hour__gte=12, departure_datetime__hour__lt=17)
        elif time_of_day == 'evening':
            rides = rides.filter(departure_datetime__hour__gte=17, departure_datetime__hour__lt=22)
        elif time_of_day == 'night':
            rides = rides.filter(departure_datetime__hour__gte=22, departure_datetime__hour__lt=6)
        
        # ========== 4. SEARCH BY PRICE ==========
        min_price = request.query_params.get('min_price', '')
        max_price = request.query_params.get('max_price', '')
        
        if min_price:
            rides = rides.filter(price_per_seat__gte=min_price)
        if max_price:
            rides = rides.filter(price_per_seat__lte=max_price)
        
        # ========== 5. SEARCH BY AVAILABLE SEATS ==========
        passengers = request.query_params.get('passengers', '1')
        try:
            passengers = int(passengers)
            rides = rides.filter(available_seats__gte=passengers)
        except ValueError:
            pass
        
        # ========== 6. SEARCH BY PREFERENCES ==========
        smoking = request.query_params.get('smoking', '')
        if smoking == 'allowed':
            rides = rides.filter(smoking_allowed=True)
        elif smoking == 'not_allowed':
            rides = rides.filter(smoking_allowed=False)
        
        gender = request.query_params.get('gender', '')
        if gender in ['male', 'female']:
            rides = rides.filter(gender_preference__in=[gender, 'any'])
        
        # ========== 7. SORTING ==========
        sort_by = request.query_params.get('sort', 'departure_time')
        sort_order = request.query_params.get('order', 'asc')
        
        if sort_by == 'price':
            order = 'price_per_seat' if sort_order == 'asc' else '-price_per_seat'
        elif sort_by == 'seats':
            order = 'available_seats' if sort_order == 'asc' else '-available_seats'
        else:
            order = 'departure_datetime' if sort_order == 'asc' else '-departure_datetime'
        
        rides = rides.order_by(order)
        
        # ========== 8. PAGINATION ==========
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        start = (page - 1) * page_size
        end = start + page_size
        total = rides.count()
        rides_page = rides[start:end]
        
        # ========== 9. FORMAT RESULTS ==========
        results = []
        for ride in rides_page:
            results.append({
                'id': ride.id,
                'driver_id': ride.driver_id,
                'departure': {
                    'id': ride.departure_city.id,
                    'name_ar': ride.departure_city.name_ar,
                    'name_fr': ride.departure_city.name_fr,
                    'wilaya_number': ride.departure_city.wilaya_number
                },
                'arrival': {
                    'id': ride.arrival_city.id,
                    'name_ar': ride.arrival_city.name_ar,
                    'name_fr': ride.arrival_city.name_fr,
                    'wilaya_number': ride.arrival_city.wilaya_number
                },
                'departure_datetime': ride.departure_datetime,
                'price_per_seat': float(ride.price_per_seat),
                'available_seats': ride.available_seats,
                'description': ride.description,
                'smoking_allowed': ride.smoking_allowed,
                'gender_preference': ride.gender_preference
            })
        
        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size,
            'results': results
        })


class CityAutocompleteView(APIView):
    """Autocomplete for city search"""
    permission_classes = []
    
    def get(self, request):
        query = request.query_params.get('q', '')
        if not query or len(query) < 2:
            return Response({'results': []})
        
        cities = City.objects.filter(
            Q(name_fr__icontains=query) |
            Q(name_ar__icontains=query)
        )[:10]
        
        results = []
        for city in cities:
            results.append({
                'id': city.id,
                'name_fr': city.name_fr,
                'name_ar': city.name_ar,
                'wilaya_number': city.wilaya_number,
                'region': city.region
            })
        
        return Response({'results': results})


class SearchStatsView(APIView):
    """Get search statistics and popular routes"""
    permission_classes = []
    
    def get(self, request):
        # Most popular routes
        popular_routes = Ride.objects.filter(
            status='scheduled',
            departure_datetime__gt=timezone.now()
        ).values(
            'departure_city__name_fr',
            'arrival_city__name_fr'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Price range
        price_stats = Ride.objects.filter(
            status='scheduled',
            departure_datetime__gt=timezone.now()
        ).aggregate(
            min_price=models.Min('price_per_seat'),
            max_price=models.Max('price_per_seat'),
            avg_price=models.Avg('price_per_seat')
        )
        
        return Response({
            'popular_routes': list(popular_routes),
            'price_range': {
                'min': float(price_stats['min_price']) if price_stats['min_price'] else 0,
                'max': float(price_stats['max_price']) if price_stats['max_price'] else 0,
                'average': float(price_stats['avg_price']) if price_stats['avg_price'] else 0
            },
            'total_available_rides': Ride.objects.filter(
                status='scheduled',
                departure_datetime__gt=timezone.now()
            ).count()
        })