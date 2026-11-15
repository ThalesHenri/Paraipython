from django.db import models


class FonteNoticia(models.Model):
    """Portal monitorado pelo robô (um feed RSS ou, no futuro, uma página raspada)."""

    class Tipo(models.TextChoices):
        RSS = "rss", "Feed RSS"
        SCRAPING = "scraping", "Scraping de página"

    nome = models.CharField(max_length=100, unique=True)
    url = models.URLField(max_length=500, verbose_name="URL do feed / página")
    site_url = models.URLField(max_length=500, blank=True, verbose_name="Site do portal")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.RSS)
    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Fonte de notícia"
        verbose_name_plural = "Fontes de notícias"
        ordering = ["nome"]

    def __str__(self):
        return self.nome
