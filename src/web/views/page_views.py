from django.utils import timezone
from django.views.generic import TemplateView

from news.models import FonteNoticia


class Sobre(TemplateView):
    template_name = "web/sobre.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["fontes"] = FonteNoticia.objects.filter(ativa=True)
        ctx["data_atual"] = timezone.localtime()
        return ctx
