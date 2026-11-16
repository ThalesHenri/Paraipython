"""Temas (seções) do jornal, na ordem em que aparecem na edição."""
from django.db import models


class Tema(models.TextChoices):
    CIDADE = "cidade", "Cidade"
    POLICIA = "policia", "Polícia"
    POLITICA = "politica", "Política"
    ECONOMIA = "economia", "Economia"
    EDUCACAO = "educacao", "Educação"
    SAUDE = "saude", "Saúde"
    CLIMA = "clima", "Clima & Ambiente"
    ESPORTES = "esportes", "Esportes"
    CULTURA = "cultura", "Cultura"


# Ordem das seções no PDF (a mesma da declaração acima).
ORDEM_TEMAS = [t.value for t in Tema]
