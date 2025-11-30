

# funds/serializers.py
from rest_framework import serializers
from decimal import Decimal
from .models import DepositBatch, LedgerEntry
from django.contrib.auth import get_user_model

User = get_user_model()

class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    bucket = serializers.ChoiceField(choices=[('reserve','Reserve'), ('liquid','Liquid')])

class TransferSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField(required=False)
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    from_bucket = serializers.ChoiceField(choices=[('liquid','Liquid'), ('reserve','Reserve')])

    def validate_amount(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("Amount must be greater than 0")
        return value
