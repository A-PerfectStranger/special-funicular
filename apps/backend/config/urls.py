from core import views
from django.urls import path

urlpatterns = [
    path("", views.home),
    path("health/live", views.live),
    path("health/ready", views.ready),
    path("v1/capabilities", views.capabilities),
]
