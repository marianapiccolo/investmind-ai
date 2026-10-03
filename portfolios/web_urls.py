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
        "performance/",
        web_views.performance,
        name="performance",
    ),
    path(
        "risk/",
        web_views.risk,
        name="risk",
    ),
]