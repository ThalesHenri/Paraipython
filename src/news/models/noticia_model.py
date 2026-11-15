from django.db import models


class Noticia(models.Model):
    """Matéria coletada de uma fonte. Guardamos só o necessário para a manchete:
    título, um resumo curto e o link para a matéria original."""

    titulo = models.CharField(max_length=300)
    link = models.URLField(max_length=500, unique=True)
    resumo = models.TextField(blank=True, verbose_name="Resumo")
    categoria = models.CharField(max_length=100, blank=True)
    conteudo_bruto = models.TextField(blank=True, verbose_name="Conteúdo bruto (HTML do feed)")
    publicado_em = models.DateTimeField(verbose_name="Publicado em", db_index=True)
    coletado_em = models.DateTimeField(auto_now_add=True, verbose_name="Coletado em")
    fonte = models.ForeignKey("FonteNoticia", on_delete=models.CASCADE, related_name="noticias")

    class Meta:
        verbose_name = "Notícia"
        verbose_name_plural = "Notícias"
        ordering = ["-publicado_em"]

    def __str__(self):
        return self.titulo
