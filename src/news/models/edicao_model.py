from django.db import models
from django.db.models import Max, Q
from django.urls import reverse

from news.temas import Tema


def upload_pdf(instance, filename):
    return f"edicoes_pdf/{filename}"


def upload_capa(instance, filename):
    return f"edicoes_pdf/capas/{filename}"


class Edicao(models.Model):
    """Uma edição do jornal (manhã ou noite): a seleção de notícias e o PDF gerado."""

    class Turno(models.TextChoices):
        # A ordem alfabética ("manha" < "noite") é também a ordem do dia.
        MANHA = "manha", "Edição da Manhã"
        NOITE = "noite", "Edição Noturna"

    titulo = models.CharField(max_length=200, default="Edição Automática • João Pessoa - PB")
    numero_edicao = models.PositiveIntegerField(unique=True, verbose_name="Nº da edição")
    data_edicao = models.DateField(verbose_name="Data da edição")
    turno = models.CharField(max_length=5, choices=Turno.choices, default=Turno.MANHA)
    fim_janela = models.DateTimeField(
        null=True, blank=True, verbose_name="Notícias até",
        help_text="Momento de corte da edição. A próxima edição começa a partir daqui.",
    )
    noticias = models.ManyToManyField("Noticia", through="EdicaoNoticia", related_name="edicoes")
    arquivo_pdf = models.FileField(upload_to=upload_pdf, blank=True, verbose_name="Arquivo PDF")
    capa = models.ImageField(upload_to=upload_capa, blank=True, verbose_name="Miniatura da capa")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Criada em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizada em")

    class Meta:
        verbose_name = "Edição"
        verbose_name_plural = "Edições"
        ordering = ["-data_edicao", "-turno"]
        constraints = [
            models.UniqueConstraint(fields=["data_edicao", "turno"], name="uma_edicao_por_turno"),
        ]

    def __str__(self):
        return f"Nº {self.numero_edicao} — {self.get_turno_display()} de {self.data_edicao:%d/%m/%Y}"

    @classmethod
    def proximo_numero(cls):
        return (cls.objects.aggregate(m=Max("numero_edicao"))["m"] or 0) + 1

    @classmethod
    def anteriores_a(cls, data, turno):
        """Edições publicadas antes de (data, turno), da mais recente para a mais antiga."""
        return cls.objects.filter(
            Q(data_edicao__lt=data) | Q(data_edicao=data, turno__lt=turno)
        ).order_by("-data_edicao", "-turno")

    @property
    def eh_noite(self):
        return self.turno == self.Turno.NOITE

    def noticias_ordenadas(self):
        return self.noticias.order_by("edicaonoticia__posicao").select_related("fonte")

    def _kwargs(self):
        return {"data": self.data_edicao.isoformat(), "turno": self.turno}

    def get_pdf_url(self):
        return reverse("news:edicao_pdf", kwargs=self._kwargs())

    def get_download_url(self):
        return reverse("news:edicao_download", kwargs=self._kwargs())

    def get_capa_url(self):
        return reverse("news:edicao_capa", kwargs=self._kwargs())


class EdicaoNoticia(models.Model):
    """Posição e seção de cada notícia na edição (posição 0 = manchete da capa)."""

    edicao = models.ForeignKey(Edicao, on_delete=models.CASCADE)
    noticia = models.ForeignKey("Noticia", on_delete=models.CASCADE)
    posicao = models.PositiveSmallIntegerField(default=0)
    tema = models.CharField(
        max_length=20, choices=Tema.choices, default=Tema.CIDADE,
        help_text="Seção em que a notícia saiu nesta edição.",
    )
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
