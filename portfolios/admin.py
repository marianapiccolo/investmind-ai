from django.contrib import admin

from portfolios.models import Asset


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "ticker",
        "name",
        "asset_type",
        "currency",
        "sector",
    )

    search_fields = (
        "ticker",
        "name",
    )

    list_filter = (
        "asset_type",
        "currency",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = (
        "ticker",
    )