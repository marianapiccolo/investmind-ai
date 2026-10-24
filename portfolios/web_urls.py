from django.urls import path

from . import web_views

app_name = "web"

urlpatterns = [
    path(
        "",
        web_views.dashboard,
        name="dashboard",
    ),
    path(
        "portfolio/",
        web_views.portfolio_management,
        name="portfolio",
    ),
    path(
        "transactions/",
        web_views.transaction_management,
        name="transactions",
    ),
    path(
        "performance/",
        web_views.performance,
        name="performance",
    ),
    path(
        "risk/",
        web_views.risk,
        name="risk",
    ),
    path(
        "diversification/",
        web_views.diversification,
        name="diversification",
    ),
    path(
        "ai-analyst/",
        web_views.ai_analyst,
        name="ai-analyst",
    ),

    path(
    "ai-reports/",
    web_views.ai_reports,
    name="ai-reports",
),
]