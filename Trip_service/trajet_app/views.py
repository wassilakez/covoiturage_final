from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import City, Vehicle, Ride, Stopover
from .serializers import (
    CitySerializer, VehicleSerializer, RideListSerializer,
    RideDetailSerializer, RideCreateSerializer, StopoverSerializer
)
from django.db.models import Q
from django.db import models


def health_check(request):
    """Health check endpoint for Consul and monitoring"""
    return JsonResponse({'status': 'healthy', 'service': 'trajet-service'})


class ReserveTripView(APIView):
    def put(self, request, pk):
        ride = get_object_or_404(Ride, id=pk)
        seats_requested = int(request.data.get("seats", 1))
        
        if ride.available_seats < seats_requested:
            return Response(
                {"error": "Not enough seats"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ride.available_seats -= seats_requested
        ride.save()
        
        return Response({
            "message": "Seats reserved successfully",
            "remaining_seats": ride.available_seats
        }, status=status.HTTP_200_OK)


class CityListView(APIView):
    """List all active cities"""
    permission_classes = []
    
    def get(self, request):
        cities = City.objects.filter(is_active=True)
        serializer = CitySerializer(cities, many=True)
        return Response(serializer.data)


class VehicleListCreateView(APIView):
    """List all vehicles for current driver or create a new vehicle"""
    permission_classes = []
    
    def get(self, request):
        driver_id = request.query_params.get('driver_id')
        owner_id = request.query_params.get('owner_id')
        
        # Accepter driver_id ou owner_id
        if driver_id:
            vehicles = Vehicle.objects.filter(owner_id=driver_id)
        elif owner_id:
            vehicles = Vehicle.objects.filter(owner_id=owner_id)
        else:
            return Response({'error': 'driver_id or owner_id required'}, status=400)
        
        serializer = VehicleSerializer(vehicles, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = VehicleSerializer(data=request.data)
        if serializer.is_valid():
            owner_id = request.data.get('owner_id')
            if not owner_id:
                return Response({'error': 'owner_id required'}, status=400)
            serializer.save(owner_id=owner_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VehicleDetailView(APIView):
    """Retrieve, update or delete a specific vehicle"""
    permission_classes = []
    
    def get(self, request, pk):
        vehicle = get_object_or_404(Vehicle, id=pk)
        serializer = VehicleSerializer(vehicle)
        return Response(serializer.data)
    
    def put(self, request, pk):
        owner_id = request.data.get('owner_id')
        if not owner_id:
            return Response({'error': 'owner_id required'}, status=400)
        vehicle = get_object_or_404(Vehicle, id=pk, owner_id=owner_id)
        serializer = VehicleSerializer(vehicle, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        owner_id = request.data.get('owner_id')
        if not owner_id:
            return Response({'error': 'owner_id required'}, status=400)
        vehicle = get_object_or_404(Vehicle, id=pk, owner_id=owner_id)
        vehicle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleCreateView(APIView):
    """Create a new vehicle (alternative endpoint)"""
    permission_classes = []
    
    def post(self, request):
        serializer = VehicleSerializer(data=request.data)
        if serializer.is_valid():
            owner_id = request.data.get('owner_id')
            if not owner_id:
                return Response({'error': 'owner_id required'}, status=400)
            serializer.save(owner_id=owner_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RideCreateView(APIView):
    """Create a new ride (driver only)"""
    permission_classes = []
    
    def post(self, request):
        serializer = RideCreateSerializer(data=request.data)
        if serializer.is_valid():
            driver_id = request.data.get('driver_id')
            if not driver_id:
                return Response({'error': 'driver_id required'}, status=status.HTTP_400_BAD_REQUEST)
            ride = serializer.save(driver_id=driver_id)
            return Response(RideDetailSerializer(ride).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RideListView(APIView):
    """List all upcoming scheduled rides"""
    permission_classes = []
    
    def get(self, request):
        rides = Ride.objects.filter(
            status='scheduled',
            departure_datetime__gt=timezone.now()
        ).select_related('departure_city', 'arrival_city')
        
        departure = request.query_params.get('departure')
        arrival = request.query_params.get('arrival')
        date = request.query_params.get('date')
        
        if departure:
            rides = rides.filter(departure_city__wilaya_number=departure)
        if arrival:
            rides = rides.filter(arrival_city__wilaya_number=arrival)
        if date:
            rides = rides.filter(departure_datetime__date=date)
        
        serializer = RideListSerializer(rides, many=True)
        return Response(serializer.data)


class AllRidesView(APIView):
    """List all rides (including past and cancelled)"""
    permission_classes = []
    
    def get(self, request):
        rides = Ride.objects.all().order_by('-created_at')
        serializer = RideListSerializer(rides, many=True)
        return Response(serializer.data)


class UpcomingRidesView(APIView):
    """List only upcoming rides (scheduled and in the future)"""
    permission_classes = []
    
    def get(self, request):
        rides = Ride.objects.filter(
            status='scheduled',
            departure_datetime__gt=timezone.now()
        ).order_by('departure_datetime')
        serializer = RideListSerializer(rides, many=True)
        return Response(serializer.data)


class PastRidesView(APIView):
    """List only completed rides"""
    permission_classes = []
    
    def get(self, request):
        rides = Ride.objects.filter(
            status='completed',
            departure_datetime__lt=timezone.now()
        ).order_by('-departure_datetime')
        serializer = RideListSerializer(rides, many=True)
        return Response(serializer.data)


class RideDetailView(APIView):
    """Get detailed information about a specific ride"""
    permission_classes = []
    
    def get(self, request, pk):
        ride = get_object_or_404(Ride, id=pk)
        serializer = RideDetailSerializer(ride)
        return Response(serializer.data)


class MyRidesView(APIView):
    """Get all rides created by the current driver"""
    permission_classes = []
    
    def get(self, request):
        driver_id = request.query_params.get('driver_id')
        if not driver_id:
            return Response({'error': 'driver_id required'}, status=400)
        rides = Ride.objects.filter(driver_id=driver_id).order_by('-created_at')
        serializer = RideListSerializer(rides, many=True)
        return Response(serializer.data)


class DriverRidesView(APIView):
    """Get all rides for a specific driver by ID"""
    permission_classes = []
    
    def get(self, request, driver_id):
        rides = Ride.objects.filter(driver_id=driver_id).order_by('-created_at')
        serializer = RideListSerializer(rides, many=True)
        return Response(serializer.data)


class RideUpdateView(APIView):
    """Update an existing ride (driver only)"""
    permission_classes = []
    
    def put(self, request, pk):
        try:
            ride = Ride.objects.get(id=pk)
        except Ride.DoesNotExist:
            return Response({'error': 'Ride not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = RideCreateSerializer(ride, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(RideDetailSerializer(ride).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RideDeleteView(APIView):
    """Permanently delete a ride"""
    permission_classes = []
    
    def delete(self, request, pk):
        try:
            ride = Ride.objects.get(id=pk)
            ride.delete()
            return Response({'message': 'Ride deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except Ride.DoesNotExist:
            return Response({'error': 'Ride not found'}, status=status.HTTP_404_NOT_FOUND)


class CancelRideView(APIView):
    """Cancel a ride (change status to cancelled)"""
    permission_classes = []
    
    def post(self, request, pk):
        driver_id = request.data.get('driver_id')
        if not driver_id:
            return Response({'error': 'driver_id required'}, status=400)
        ride = get_object_or_404(Ride, id=pk, driver_id=driver_id)
        ride.status = 'cancelled'
        ride.save()
        return Response({'message': 'Ride cancelled successfully'}, status=status.HTTP_200_OK)


class CityDetailView(APIView):
    """Get details of a specific city"""
    permission_classes = []
    
    def get(self, request, pk):
        city = get_object_or_404(City, id=pk)
        serializer = CitySerializer(city)
        return Response(serializer.data)


class CityCreateView(APIView):
    """Create a new city (admin only)"""
    permission_classes = []
    
    def post(self, request):
        serializer = CitySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CityUpdateView(APIView):
    """Update an existing city (admin only)"""
    permission_classes = []
    
    def put(self, request, pk):
        city = get_object_or_404(City, id=pk)
        serializer = CitySerializer(city, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CityDeleteView(APIView):
    """Delete a city (admin only)"""
    permission_classes = []
    
    def delete(self, request, pk):
        city = get_object_or_404(City, id=pk)
        city.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StopoverListView(APIView):
    """List all stopovers for a specific ride"""
    permission_classes = []
    
    def get(self, request, ride_id):
        ride = get_object_or_404(Ride, id=ride_id)
        stopovers = ride.stopovers.all().order_by('order')
        serializer = StopoverSerializer(stopovers, many=True)
        return Response(serializer.data)


class StopoverCreateView(APIView):
    """Add a stopover to a ride"""
    permission_classes = []
    
    def post(self, request, ride_id):
        ride = get_object_or_404(Ride, id=ride_id)
        data = request.data.copy()
        data['ride'] = ride.id
        
        serializer = StopoverSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StopoverDeleteView(APIView):
    """Delete a stopover"""
    permission_classes = []
    
    def delete(self, request, pk):
        stopover = get_object_or_404(Stopover, id=pk)
        stopover.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DriverStatsView(APIView):
    """Get statistics for the current driver (total rides, earnings, etc.)"""
    permission_classes = []
    
    def get(self, request):
        driver_id = request.query_params.get('driver_id')
        if not driver_id:
            return Response({'error': 'driver_id required'}, status=400)
        
        total_rides = Ride.objects.filter(driver_id=driver_id).count()
        completed_rides = Ride.objects.filter(driver_id=driver_id, status='completed').count()
        cancelled_rides = Ride.objects.filter(driver_id=driver_id, status='cancelled').count()
        
        total_earnings = Ride.objects.filter(
            driver_id=driver_id, 
            status='completed'
        ).aggregate(total=models.Sum('total_revenue'))['total'] or 0
        
        total_passengers = Ride.objects.filter(
            driver_id=driver_id,
            status='completed'
        ).aggregate(total=models.Sum('total_bookings'))['total'] or 0
        
        return Response({
            'driver_id': driver_id,
            'total_rides': total_rides,
            'completed_rides': completed_rides,
            'cancelled_rides': cancelled_rides,
            'total_earnings': float(total_earnings),
            'total_passengers': total_passengers,
            'active_rides': Ride.objects.filter(
                driver_id=driver_id, 
                status='scheduled', 
                departure_datetime__gt=timezone.now()
            ).count()
        })