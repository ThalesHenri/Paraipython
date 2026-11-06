from django.db import models


class Noticia(models.Model):
    titulo = models.CharField(max_length=200)
    link = models.URLField()
    resumo = models.TextField(blank=True, null=True, verbose_name='Resumo')
    conteudo_Bruto = models.TextField() #HTMLField
    publicado_em = models.DateTimeField(verbose_name='Publicado em')
    coletado_em = models.DateTimeField(auto_now_add=True, verbose_name='Coletado em')
    fonte = models.ForeignKey('FonteNoticia', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Notícia'
        verbose_name_plural = 'Notícias'
        ordering = ['-publicado_em']
        
    def __str__(self):
        return self.titulo