from django.db import models
from django.db.models import Max
from django.urls import reverse


def upload_pdf(instance, filename):
    return f"edicoes_pdf/{filename}"


def upload_capa(instance, filename):
    return f"edicoes_pdf/capas/{filename}"


class Edicao(models.Model):
    """Uma edição diária do jornal: a seleção de notícias do dia e o PDF gerado."""

    titulo = models.CharField(max_length=200, default="Edição Diária Automática • João Pessoa - PB")
    numero_edicao = models.PositiveIntegerField(unique=True, verbose_name="Nº da edição")
    data_edicao = models.DateField(unique=True, verbose_name="Data da edição")
    noticias = models.ManyToManyField("Noticia", through="EdicaoNoticia", related_name="edicoes")
    arquivo_pdf = models.FileField(upload_to=upload_pdf, blank=True, verbose_name="Arquivo PDF")
    capa = models.ImageField(upload_to=upload_capa, blank=True, verbose_name="Miniatura da capa")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Criada em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizada em")

    class Meta:
        verbose_name = "Edição"
        verbose_name_plural = "Edições"
        ordering = ["-data_edicao"]

    def __str__(self):
        return f"Edição Nº {self.numero_edicao} — {self.data_edicao:%d/%m/%Y}"

    @classmethod
    def proximo_numero(cls):
        return (cls.objects.aggregate(m=Max("numero_edicao"))["m"] or 0) + 1

    def noticias_ordenadas(self):
        return self.noticias.order_by("edicaonoticia__posicao").select_related("fonte")

    def get_pdf_url(self):
        return reverse("news:edicao_pdf", kwargs={"data": self.data_edicao.isoformat()})

    def get_download_url(self):
        return reverse("news:edicao_download", kwargs={"data": self.data_edicao.isoformat()})

    def get_capa_url(self):
        return reverse("news:edicao_capa", kwargs={"data": self.data_edicao.isoformat()})


class EdicaoNoticia(models.Model):
    """Posição de cada notícia na edição (0 = manchete principal)."""

    edicao = models.ForeignKey(Edicao, on_delete=models.CASCADE)
    noticia = models.ForeignKey("Noticia", on_delete=models.CASCADE)
    posicao = models.PositiveSmallIntegerField(default=0)
    outras_fontes = models.CharField(
        max_length=300, blank=True,
        help_text="Outros portais que também deram a notícia (usado no peso de relevância).",
    )
    outros_links = models.JSONField(
        default=list, blank=True,
        help_text='Links da mesma pauta em outros portais: [{"fonte": ..., "link": ...}].',
    )

    class Meta:
        ordering = ["posicao"]
        unique_together = [("edicao", "noticia")]
