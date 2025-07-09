# medications/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.medication_list, name="medication_list"),
]