from django.utils import timezone
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Transaction

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'healthy', 'service': 'payment-service'})

# ==================== CRÉATION PAIEMENT CARTE ====================
@api_view(['POST'])
@permission_classes([AllowAny])
def create_payment(request):
    """Créer un paiement avec blocage des fonds (status='held')"""
    try:
        data = request.data
        user_id = data.get('user_id')
        amount = data.get('amount')
        payment_method = data.get('payment_method')
        booking_id = str(data.get('booking_id'))

        trip_id = data.get('trip_id')
        
        # Vérifier si un paiement existe déjà
        existing = Transaction.objects.filter(
            booking_id=booking_id,
            status__in=['pending', 'held', 'completed']
        ).first()
        
        if existing:
            return Response({
                'success': False,
                'error': 'Un paiement existe déjà',
                'transaction_id': str(existing.id)
            }, status=400)
        
        # Créer la transaction avec status 'held' (fonds bloqués)
        transaction = Transaction.objects.create(
            booking_id=booking_id,
            user_id=user_id,
            amount=amount,
            payment_method=payment_method,
            trip_id=trip_id,
            status='held',
            commission=float(amount) * 0.10,  # Commission 10%
            driver_amount=float(amount) * 0.90
        )
        
        return Response({
            'success': True,
            'transaction_id': transaction.id,
            'status': 'held',
            'message': 'Fonds bloqués avec succès'
        }, status=201)
        
    except Exception as e:
        logger.error(f"Erreur création paiement: {str(e)}")
        return Response({'error': str(e)}, status=400)

# ==================== LIBÉRATION FONDS (FIN TRAJET) ====================
@api_view(['POST'])
@permission_classes([AllowAny])
def release_payment(request):
    """Libérer les fonds au conducteur après trajet terminé"""
    try:
        transaction_id = request.data.get('transaction_id')
        transaction = Transaction.objects.get(id=transaction_id)
        
        if transaction.status != 'held':
            return Response({
                'error': f'Transaction non bloquée (status: {transaction.status})'
            }, status=400)
        
        transaction.status = 'released'
        transaction.released_at = timezone.now()
        transaction.save()
        
        return Response({
            'success': True,
            'status': 'released',
            'amount': float(transaction.amount),
            'commission': float(transaction.commission),
            'driver_amount': float(transaction.driver_amount),
            'message': f'Paiement libéré au conducteur'
        }, status=200)
        
    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction non trouvée'}, status=404)
    except Exception as e:
        logger.error(f"Erreur libération: {str(e)}")
        return Response({'error': str(e)}, status=400)

# ==================== REMBOURSEMENT ====================
@api_view(['POST'])
def refund_payment(request, transaction_id):
    """Rembourser un paiement"""
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        reason = request.data.get('reason', 'Remboursement')
        
        if transaction.status not in ['held', 'completed']:
            return Response({
                'error': f'Transaction non remboursable (status: {transaction.status})'
            }, status=400)
        
        transaction.status = 'refunded'
        transaction.refund_reason = reason
        transaction.refunded_at = timezone.now()
        transaction.save()
        
        return Response({
            'success': True,
            'status': 'refunded',
            'amount': float(transaction.amount),
            'message': f'Remboursement de {transaction.amount} DA effectué'
        }, status=200)
        
    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction non trouvée'}, status=404)
    except Exception as e:
        logger.error(f"Erreur remboursement: {str(e)}")
        return Response({'error': str(e)}, status=400)

# ==================== REMBOURSEMENT PARTIEL (50%) ====================
@api_view(['POST'])
def partial_refund_payment(request, transaction_id):
    """Remboursement partiel (50%)"""
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        reason = request.data.get('reason', 'Annulation tardive')
        
        if transaction.status != 'held':
            return Response({
                'error': f'Transaction non remboursable (status: {transaction.status})'
            }, status=400)
        
        refund_amount = float(transaction.amount) * 0.50
        
        transaction.status = 'partial_refund'
        transaction.refund_amount = refund_amount
        transaction.refund_reason = reason
        transaction.refunded_at = timezone.now()
        transaction.save()
        
        return Response({
            'success': True,
            'status': 'partial_refund',
            'refunded_amount': refund_amount,
            'remaining_held': float(transaction.amount) - refund_amount,
            'message': f'Remboursement partiel de {refund_amount} DA effectué'
        }, status=200)
        
    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction non trouvée'}, status=404)
    except Exception as e:
        logger.error(f"Erreur remboursement partiel: {str(e)}")
        return Response({'error': str(e)}, status=400)

# ==================== ANNULATION AVEC CALCUL AUTO ====================
@api_view(['POST'])
def cancel_booking_refund(request):
    """Annulation avec calcul automatique du remboursement"""
    try:
        booking_id = request.data.get('booking_id')
        canceller = request.data.get('canceller')  # 'passenger' ou 'driver'
        hours_before_departure = request.data.get('hours_before_departure', 0)
        
        transaction = Transaction.objects.get(booking_id=booking_id)
        
        if canceller == 'passenger':
            if hours_before_departure >= 24:
                refund_percent = 100
                transaction.status = 'refunded'
            elif hours_before_departure > 0:
                refund_percent = 50
                transaction.status = 'partial_refund'
            else:
                refund_percent = 0
                transaction.status = 'cancelled'
        else:  # driver cancels
            refund_percent = 100
            transaction.status = 'refunded'
        
        refund_amount = (float(transaction.amount) * refund_percent) / 100
        
        transaction.refund_amount = refund_amount
        transaction.refund_reason = f"Annulation par {canceller}"
        transaction.refunded_at = timezone.now()
        transaction.save()
        
        return Response({
            'success': True,
            'refunded': refund_amount,
            'percent': refund_percent,
            'transaction_id': str(transaction.id),
            'status': transaction.status
        }, status=200)
        
    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction non trouvée'}, status=404)
    except Exception as e:
        logger.error(f"Erreur cancel refund: {str(e)}")
        return Response({'error': str(e)}, status=400)

# ==================== ADMIN : BLOQUER PAIEMENT ====================
@api_view(['POST'])
@permission_classes([AllowAny])
def admin_block_payment(request):
    """Admin bloque un paiement"""
    try:
        transaction_id = request.data.get('transaction_id')
        reason = request.data.get('reason', 'Bloqué par admin')
        
        transaction = Transaction.objects.get(id=transaction_id)
        transaction.status = 'blocked'
        transaction.block_reason = reason
        transaction.blocked_at = timezone.now()
        transaction.save()
        
        return Response({
            'success': True,
            'status': 'blocked',
            'message': f'Paiement bloqué: {reason}'
        }, status=200)
        
    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction non trouvée'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_transaction(request, transaction_id):
    """Récupérer les détails d'une transaction"""
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        return Response({
            'id': transaction.id,
            'status': transaction.status,
            'amount': float(transaction.amount),
            'payment_method': transaction.payment_method,
            'commission': float(transaction.commission) if transaction.commission else 0,
            'driver_amount': float(transaction.driver_amount) if transaction.driver_amount else 0,
            'created_at': transaction.created_at,
            'released_at': transaction.released_at,
            'refunded_at': transaction.refunded_at,
            'refund_amount': float(transaction.refund_amount) if transaction.refund_amount else 0,
            'refund_reason': transaction.refund_reason
        })
    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction non trouvée'}, status=404)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_wallet(request):
    return Response({'balance': 0, 'status': 'ok'})