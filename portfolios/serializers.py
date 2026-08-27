from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Asset, Portfolio, Transaction
from .services import create_transaction

class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = [
            "id",
            "name",
            "currency",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

class TransactionSerializer(serializers.ModelSerializer):
    portfolio = serializers.PrimaryKeyRelatedField(
        queryset=Portfolio.objects.all()
    )

    asset = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects.all()
    )

    class Meta:
        model = Transaction
        fields = [
            "id",
            "portfolio",
            "asset",
            "transaction_type",
            "quantity",
            "price",
            "transaction_date",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_portfolio(self, portfolio):
        request = self.context["request"]

        if portfolio.user != request.user:
            raise serializers.ValidationError(
                "You cannot create transactions for this portfolio."
            )

        return portfolio

    def create(self, validated_data):
        try:
            return create_transaction(**validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.messages
            ) from exc