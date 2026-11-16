from django.conf import settings
from django.utils import timezone
from django.views.generic import ListView, TemplateView

from news.models import Edicao


def edicoes_publicadas():
    return Edicao.objects.exclude(arquivo_pdf="")


def proxima_edicao(agora=None):
    """Nome e horário da próxima edição, para a mensagem de "ainda tá passando"."""
    agora = timezone.localtime(agora or timezone.now())
    cfg = settings.PARAIPYTHON
    manha, noite = cfg["HORARIO_MANHA"], cfg["HORARIO_NOITE"]
    hora_atual = agora.strftime("%H:%M")
    if manha <= hora_atual < noite:
        return {"nome": Edicao.Turno.NOITE.label, "hora": noite}
    return {"nome": Edicao.Turno.MANHA.label, "hora": manha}


class HomeView(TemplateView):
    template_name = "news/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        atual = edicoes_publicadas().first()  # a mais recente (data e turno)
        eh_de_hoje = bool(atual and atual.data_edicao == hoje)
        outra_de_hoje = None
        if eh_de_hoje and atual.eh_noite:
            outra_de_hoje = edicoes_publicadas().filter(data_edicao=hoje, turno=Edicao.Turno.MANHA).first()
        ctx.update(
            {
                "edicao_hoje": atual if eh_de_hoje else None,
                "ultima_edicao": None if eh_de_hoje else atual,
                "outra_de_hoje": outra_de_hoje,
                "proxima": proxima_edicao(),
                "manchetes": atual.noticias_ordenadas()[:8] if atual else [],
                "data_atual": timezone.localtime(),
            }
        )
        return ctx


class AcervoView(ListView):
    template_name = "news/acervo.html"
    context_object_name = "edicoes"
    paginate_by = 24  # 12 dias de edições

    def get_queryset(self):
        # Dias do mais recente para o mais antigo; dentro do dia, manhã antes da noite.
        return edicoes_publicadas().order_by("-data_edicao", "turno")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["data_atual"] = timezone.localtime()
        return ctx
