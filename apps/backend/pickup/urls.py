from django.urls import path

from pickup import views

urlpatterns = [
    path("pickup/capabilities", views.capabilities),
    path("authorizations/<uuid:authorization_id>/issue-qr", views.issue_qr),
    path("authorizations/<uuid:authorization_id>/reschedule", views.reschedule),
    path("guard/resolve-qr", views.resolve),
    path("guard/caregiver-photo", views.photo),
    path("guard/confirm-pickup", views.confirm),
    path("guard/operations/<uuid:operation_id>", views.operation),
    path("guard/operations/<uuid:operation_id>/report-handover", views.report),
]
