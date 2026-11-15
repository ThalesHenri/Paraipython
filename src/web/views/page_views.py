from django.conf import settings
from django.templatetags.static import static
from django.utils import timezone
from django.views.generic import TemplateView

from news.models import FonteNoticia
from web.pix import payload_pix, qr_svg_data_uri


def contexto_apoio():
    """Dados da seção "Apoie" a partir do settings.APOIO (que lê o .env)."""
    cfg = settings.APOIO
    copia_e_cola = payload_pix(
        chave=cfg["PIX_CHAVE"],
        nome=cfg["PIX_NOME"],
        cidade=cfg["PIX_CIDADE"],
        descricao=cfg["PIX_DESCRICAO"],
    )
    # Se você tiver a imagem do QR gerada pelo seu banco, ela tem prioridade.
    if cfg["PIX_QR_IMAGEM"]:
        pix_qr = static(cfg["PIX_QR_IMAGEM"])
    else:
        pix_qr = qr_svg_data_uri(copia_e_cola)

    link_qr = qr_svg_data_uri(cfg["LINK_URL"]) if cfg["LINK_URL"] else None
    return {
        "ficticio": cfg["FICTICIO"],
        "pix_chave": cfg["PIX_CHAVE"],
        "pix_nome": cfg["PIX_NOME"],
        "pix_copia_e_cola": copia_e_cola,
        "pix_qr": pix_qr,
        "link_nome": cfg["LINK_NOME"],
        "link_url": cfg["LINK_URL"],
        "link_qr": link_qr,
    }


class Sobre(TemplateView):
    template_name = "web/sobre.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["fontes"] = FonteNoticia.objects.filter(ativa=True)
        ctx["data_atual"] = timezone.localtime()
        ctx["apoio"] = contexto_apoio()
        return ctx
