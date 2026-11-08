from django.urls import path

from identity import views

urlpatterns = [
    path("v1/auth/mobile/start", views.mobile_start),
    path("v1/auth/mobile/exchange", views.mobile_exchange),
    path("v1/auth/refresh", views.mobile_refresh),
    path("v1/auth/logout", views.mobile_logout),
    path("v1/me", views.me),
    path("v1/system/school-access-records", views.access_records),
    path("auth/login", views.web_login, name="identity-login"),
    path("auth/callback", views.web_callback, name="identity-callback"),
    path("auth/logout", views.web_logout, name="identity-logout"),
    path("portal/", views.portal, name="identity-portal"),
]
