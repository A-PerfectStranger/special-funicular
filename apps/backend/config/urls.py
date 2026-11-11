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

if settings.E2_FAMILY_ENABLED:
    from django.urls import include

    urlpatterns += [path("v1/", include("authorization.urls"))]
    urlpatterns += [path("v1/", include("notification_worker.urls"))]

if settings.E3_PICKUP_ENABLED:
    from django.urls import include

    urlpatterns += [path("v1/", include("pickup.urls"))]

if settings.E4_OPERATIONS_ENABLED:
    from django.urls import include

    urlpatterns += [path("v1/", include("pickup.record_urls"))]
