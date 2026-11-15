"""Entrega os arquivos das edições pelo próprio Django.

No cPanel (Passenger), a pasta media/ não é servida automaticamente quando DEBUG=False.
Servir por estas views resolve sem mexer em .htaccess e ainda dá URLs bonitas:
    /edicao/2026-11-15/pdf/       → abre no navegador
    /edicao/2026-11-15/download/  → baixa o arquivo
    /edicao/2026-11-15/capa.png   → miniatura da primeira página
"""
from datetime import date

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from news.models import Edicao


def _edicao(data):
    try:
        dia = date.fromisoformat(data)
    except ValueError:
        raise Http404("Data inválida.")
    return get_object_or_404(Edicao, data_edicao=dia)


def _arquivo(campo, **kwargs):
    if not campo:
        raise Http404("Arquivo ainda não gerado.")
    try:
        return FileResponse(campo.open("rb"), **kwargs)
    except FileNotFoundError:
        raise Http404("Arquivo não encontrado no disco.")


@require_GET
def edicao_pdf(request, data):
    edicao = _edicao(data)
    return _arquivo(edicao.arquivo_pdf, content_type="application/pdf",
                    filename=f"expresso-pb-{edicao.data_edicao}.pdf")


@require_GET
def edicao_download(request, data):
    edicao = _edicao(data)
    return _arquivo(edicao.arquivo_pdf, as_attachment=True, content_type="application/pdf",
                    filename=f"expresso-pb-{edicao.data_edicao}.pdf")


@require_GET
def edicao_capa(request, data):
    edicao = _edicao(data)
    return _arquivo(edicao.capa, content_type="image/png")
