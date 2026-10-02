from django.urls import path

from . import web_views

app_name = "web"

urlpatterns = [
    path(
        "",
        web_views.dashboard,
        name="dashboard",
    ),
]