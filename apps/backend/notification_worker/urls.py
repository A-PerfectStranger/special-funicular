from django.urls import path

from notification_worker import views

urlpatterns = [path("me/notification-device", views.register)]
