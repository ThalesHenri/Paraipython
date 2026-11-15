from django.utils import timezone
from django.views.generic import ListView, TemplateView

from news.models import Edicao


def edicoes_publicadas():
    return Edicao.objects.exclude(arquivo_pdf="")


class HomeView(TemplateView):
    template_name = "news/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        edicao_hoje = edicoes_publicadas().filter(data_edicao=hoje).first()
        destaque = edicao_hoje or edicoes_publicadas().first()
        ctx.update(
            {
                "edicao_hoje": edicao_hoje,
                "ultima_edicao": None if edicao_hoje else destaque,
                "manchetes": destaque.noticias_ordenadas()[:8] if destaque else [],
                "data_atual": timezone.localtime(),
            }
        )
        return ctx


class AcervoView(ListView):
    template_name = "news/acervo.html"
    context_object_name = "edicoes"
    paginate_by = 24

    def get_queryset(self):
        return edicoes_publicadas().order_by("-data_edicao")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["data_atual"] = timezone.localtime()
        return ctx
