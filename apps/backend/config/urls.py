from core import views
from django.urls import path

urlpatterns = [
    path("", views.home, name="home"),
    path("health/live", views.live, name="live"),
    path("health/ready", views.ready, name="ready"),
    path("v1/capabilities", views.capabilities, name="capabilities"),
]
