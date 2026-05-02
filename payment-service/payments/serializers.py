# payments/serializers.py

from rest_framework import serializers
from .models import Transaction, Wallet, Refund, PaymentMethod, PaymentStatus


class TransactionSerializer(serializers.ModelSerializer):
    """
    Sérializer pour les transactions
    """
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 
            'booking_id', 
            'user_id', 
            'amount', 
            'commission', 
            'driver_amount',
            'currency', 
            'payment_method',
            'payment_method_display',
            'status',
            'status_display',
            'transaction_id',
            'payment_gateway_response',
            'metadata',
            'initiated_at',
            'completed_at',
            'failed_at',
            'failure_reason'
        ]
        read_only_fields = [
            'id', 
            'commission', 
            'driver_amount', 
            'status', 
            'initiated_at',
            'completed_at',
            'failed_at'
        ]


class CreatePaymentSerializer(serializers.Serializer):
    """
    Sérializer pour la création d'un paiement
    """
    booking_id = serializers.CharField(required=True, help_text="ID de la réservation")

    amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=True,
        help_text="Montant à payer en DZD"
    )
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices, 
        required=True,
        help_text="Méthode de paiement (cash, cib, edahabia, ccp, wallet)"
    )
    metadata = serializers.JSONField(
        required=False, 
        default=dict,
        help_text="Informations supplémentaires (trajet, chauffeur, etc.)"
    )
    
    def validate_amount(self, value):
        """Valider que le montant est positif"""
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à 0")
        return value
    
    def validate_booking_id(self, value):
        """Valider le format de l'ID de réservation"""
        if not value:
            raise serializers.ValidationError("L'ID de réservation est requis")
        return value


class ConfirmPaymentSerializer(serializers.Serializer):
    """
    Sérializer pour la confirmation d'un paiement
    """
    transaction_id = serializers.UUIDField(required=True, help_text="ID de la transaction")
    payment_confirmation = serializers.DictField(
        required=False, 
        default=dict,
        help_text="Informations de confirmation (référence, etc.)"
    )
    
    def validate_transaction_id(self, value):
        """Valider que la transaction existe et est en attente"""
        try:
            transaction = Transaction.objects.get(id=value)
            if transaction.status not in [PaymentStatus.PENDING, PaymentStatus.PROCESSING]:
                raise serializers.ValidationError(
                    f"Cette transaction ne peut pas être confirmée (statut: {transaction.status})"
                )
        except Transaction.DoesNotExist:
            raise serializers.ValidationError("Transaction non trouvée")
        return value


class WalletSerializer(serializers.ModelSerializer):
    """
    Sérializer pour le portefeuille
    """
    formatted_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = [
            'id', 
            'user_id', 
            'balance',
            'formatted_balance',
            'created_at', 
            'updated_at'
        ]
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']
    
    def get_formatted_balance(self, obj):
        """Retourner le solde formaté"""
        return f"{obj.balance:,.2f} DZD"


class AddBalanceSerializer(serializers.Serializer):
    """
    Sérializer pour ajouter du solde au portefeuille
    """
    amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=True,
        help_text="Montant à ajouter en DZD"
    )
    
    def validate_amount(self, value):
        """Valider que le montant est positif"""
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à 0")
        if value > 100000:
            raise serializers.ValidationError("Le montant maximum est de 100 000 DZD")
        return value


class RefundSerializer(serializers.ModelSerializer):
    """
    Sérializer pour les remboursements
    """
    transaction_id = serializers.UUIDField(source='transaction.id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Refund
        fields = [
            'id', 
            'transaction_id',
            'transaction',
            'amount', 
            'reason', 
            'status',
            'status_display',
            'initiated_at', 
            'completed_at'
        ]
        read_only_fields = ['id', 'initiated_at', 'completed_at']


class CreateRefundSerializer(serializers.Serializer):
    """
    Sérializer pour demander un remboursement
    """
    reason = serializers.CharField(
        required=False, 
        max_length=255,
        help_text="Raison du remboursement"
    )
    
    def validate_reason(self, value):
        """Valider la raison"""
        if value and len(value) < 5:
            raise serializers.ValidationError("La raison doit contenir au moins 5 caractères")
        return value or "Remboursement demandé par l'utilisateur"


class PaymentStatusSerializer(serializers.Serializer):
    """
    Sérializer pour le statut de paiement
    """
    transaction_id = serializers.UUIDField()
    booking_id = serializers.UUIDField()
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    receipt_url = serializers.URLField(required=False)
    message = serializers.CharField(required=False)


class TransactionHistorySerializer(serializers.Serializer):
    """
    Sérializer pour l'historique des transactions (format simplifié)
    """
    id = serializers.UUIDField()
    date = serializers.DateTimeField(source='initiated_at')
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    type = serializers.SerializerMethodField()
    status = serializers.CharField()
    description = serializers.SerializerMethodField()
    
    def get_type(self, obj):
        """Déterminer le type de transaction"""
        if obj.payment_method == 'wallet' and obj.booking_id is None:
            return 'recharge'
        elif obj.status == PaymentStatus.COMPLETED:
            return 'payment'
        elif obj.status == PaymentStatus.REFUNDED:
            return 'refund'
        return 'unknown'
    
    def get_description(self, obj):
        """Générer une description lisible"""
        if obj.metadata:
            from_city = obj.metadata.get('from_city', '')
            to_city = obj.metadata.get('to_city', '')
            if from_city and to_city:
                return f"Trajet {from_city} → {to_city}"
        return f"Transaction {obj.id}"


class PaymentMethodSerializer(serializers.Serializer):
    """
    Sérializer pour les méthodes de paiement disponibles
    """
    code = serializers.CharField()
    name = serializers.CharField()
    icon = serializers.CharField(required=False)
    enabled = serializers.BooleanField(default=True)
    requires_confirmation = serializers.BooleanField(default=True)
    
    @classmethod
    def get_payment_methods(cls):
        """Retourner la liste des méthodes de paiement disponibles"""
        return [
            {
                'code': 'cash',
                'name': 'Espèces',
                'icon': '💰',
                'enabled': True,
                'requires_confirmation': True,
                'description': 'Paiement en espèces au chauffeur'
            },
            {
                'code': 'cib',
                'name': 'Carte Bancaire',
                'icon': '💳',
                'enabled': True,
                'requires_confirmation': True,
                'description': 'Paiement par carte bancaire'
            },
            {
                'code': 'edahabia',
                'name': 'Edahabia',
                'icon': '🏦',
                'enabled': True,
                'requires_confirmation': True,
                'description': 'Paiement via Edahabia'
            },
            {
                'code': 'ccp',
                'name': 'CCP',
                'icon': '📮',
                'enabled': True,
                'requires_confirmation': True,
                'description': 'Paiement par virement CCP'
            },
            {
                'code': 'wallet',
                'name': 'Portefeuille',
                'icon': '👛',
                'enabled': True,
                'requires_confirmation': False,
                'description': 'Paiement via votre portefeuille virtuel'
            }
        ]


class ReceiptSerializer(serializers.Serializer):
    """
    Sérializer pour le reçu PDF
    """
    transaction_id = serializers.UUIDField()
    download_url = serializers.URLField()
    generated_at = serializers.DateTimeField()
    file_size = serializers.IntegerField(required=False)