from django.db import models

class FonteNoticia(models.Model):
    nome = models.CharField(max_length=100)
    ativa = models.BooleanField(default=True)
    url = models.URLField()
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    def __str__(self):
        return self.nome

    