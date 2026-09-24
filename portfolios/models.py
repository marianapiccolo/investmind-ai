from django.conf import settings
from django.db import models


class Portfolio(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    currency = models.CharField(max_length=3, default="EUR")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Asset(models.Model):
    class AssetType(models.TextChoices):
        STOCK = "STOCK", "Stock"
        ETF = "ETF", "ETF"
        BOND = "BOND", "Bond"
        FUND = "FUND", "Fund"
        CRYPTO = "CRYPTO", "Cryptocurrency"
        OTHER = "OTHER", "Other"

    ticker = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    asset_type = models.CharField(
        max_length=20,
        choices=AssetType.choices,
    )
    sector = models.CharField(max_length=100, blank=True)
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ticker} - {self.name}"


class Position(models.Model):
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="positions",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="positions",
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=8,
    )
    average_price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "asset"],
                name="unique_asset_per_portfolio",
            )
        ]

    def __str__(self):
        return f"{self.portfolio.name} - {self.asset.ticker}"


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=8,
    )
    price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
    )
    transaction_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="transaction_quantity_greater_than_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(price__gt=0),
                name="transaction_price_greater_than_zero",
            ),
        ]

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} {self.asset.ticker}"


class MarketPrice(models.Model):
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="market_prices",
    )

    date = models.DateField()

    close = models.DecimalField(
        max_digits=20,
        decimal_places=8,
    )

    provider = models.CharField(
        max_length=50,
        default="alpha_vantage",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

        constraints = [
            models.UniqueConstraint(
                fields=["asset", "date"],
                name="unique_market_price_per_asset_date",
            )
        ]

    def __str__(self):
        return f"{self.asset.ticker} {self.date} {self.close}"


class AIReport(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"
        FAILED = "FAILED", "Failed"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="ai_reports",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    model = models.CharField(max_length=100)

    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
    )

    context_snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    report = models.JSONField(
        null=True,
        blank=True,
    )

    evaluation = models.JSONField(
        null=True,
        blank=True,
    )

    error_message = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"AI Report {self.id} - {self.portfolio.name} - {self.status}"


class AIConversation(models.Model):
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "-updated_at",
            "-created_at",
        ]

    def __str__(self):
        return f"AI Conversation {self.id} - {self.portfolio.name}"


class AIMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [
            "created_at",
            "id",
        ]

    def __str__(self):
        return f"{self.role} message {self.id} - conversation {self.conversation_id}"
