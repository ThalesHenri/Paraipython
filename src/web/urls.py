from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("sobre/", views.Sobre.as_view(), name="sobre"),
]
