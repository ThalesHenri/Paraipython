from django.db import models
import os

def upload_to(instance, filename):
    # Define o caminho de upload para os arquivos de edição
    return os.path.join('edicoes_pdf', filename)

class Edicao(models.Model):
    titulo = models.CharField(max_length=200)
    numero_edicao = models.IntegerField()
    data_edicao = models.DateField()
    arquivo_pdf = models.FileField(upload_to=upload_to, verbose_name='Arquivo PDF')
    noticias = models.ManyToManyField('Noticia', related_name='edicoes')
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    fonte = models.ForeignKey('FonteNoticia', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Edição'
        verbose_name_plural = 'Edições'
        ordering = ['-data_edicao']
    def __str__(self):
        return f"Edição de Nº{self.numero_edicao}-{self.data_edicao}"