from django.urls import path

from pickup import records

urlpatterns = [
    path("school/pickup-records", records.school_records),
    path("me/pickups", records.parent_records),
    path("operations/capabilities", records.capabilities),
]
