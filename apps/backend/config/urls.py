from core import views
from django.conf import settings
from django.urls import URLPattern, URLResolver, path

urlpatterns: list[URLPattern | URLResolver] = [
    path("", views.home, name="home"),
    path("health/live", views.live, name="live"),
    path("health/ready", views.ready, name="ready"),
    path("v1/capabilities", views.capabilities, name="capabilities"),
]

if settings.E1_IDENTITY_ENABLED:
    from django.urls import include

    urlpatterns += [path("", include("identity.urls"))]
