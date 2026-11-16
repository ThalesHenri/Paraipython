from django.urls import path

from . import views

app_name = "news"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("acervo/", views.AcervoView.as_view(), name="acervo"),
    path("edicao/<str:data>/<str:turno>/pdf/", views.edicao_pdf, name="edicao_pdf"),
    path("edicao/<str:data>/<str:turno>/download/", views.edicao_download, name="edicao_download"),
    path("edicao/<str:data>/<str:turno>/capa.png", views.edicao_capa, name="edicao_capa"),
    # URLs antigas (antes das edições da manhã e da noite)
    path("edicao/<str:data>/pdf/", views.edicao_sem_turno, {"destino": "pdf"}),
    path("edicao/<str:data>/download/", views.edicao_sem_turno, {"destino": "download"}),
    path("edicao/<str:data>/capa.png", views.edicao_sem_turno, {"destino": "capa"}),
]
