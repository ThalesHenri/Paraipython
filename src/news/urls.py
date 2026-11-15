from django.urls import path

from . import views

app_name = "news"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("acervo/", views.AcervoView.as_view(), name="acervo"),
    path("edicao/<str:data>/pdf/", views.edicao_pdf, name="edicao_pdf"),
    path("edicao/<str:data>/download/", views.edicao_download, name="edicao_download"),
    path("edicao/<str:data>/capa.png", views.edicao_capa, name="edicao_capa"),
]
