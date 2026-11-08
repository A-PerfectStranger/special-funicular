from django.urls import path

from authorization import views

urlpatterns = [
    path("family/capabilities", views.capabilities),
    path("activation/redeem", views.redeem),
    path("students", views.students),
    path("students/<uuid:student_id>/family", views.records),
    path("caregivers", views.create_caregiver),
    path("caregivers/<uuid:caregiver_id>/update", views.update_caregiver),
    path("caregivers/<uuid:caregiver_id>/photo", views.photo),
    path("authorizations", views.create_authorization),
    path("authorizations/<uuid:authorization_id>/revoke", views.revoke),
]
