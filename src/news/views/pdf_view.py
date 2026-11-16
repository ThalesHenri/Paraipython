"""Entrega os arquivos das edições pelo próprio Django.

No cPanel (Passenger), a pasta media/ não é servida automaticamente quando DEBUG=False.
Servir por estas views resolve sem mexer em .htaccess e ainda dá URLs bonitas:
    /edicao/2026-11-15/manha/pdf/       → abre no navegador
    /edicao/2026-11-15/noite/download/  → baixa o arquivo
    /edicao/2026-11-15/manha/capa.png   → miniatura da primeira página

As URLs antigas, sem o turno (/edicao/2026-11-15/pdf/), redirecionam para a edição
mais recente daquele dia, para não quebrar links já compartilhados.
"""
from datetime import date

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET

from news.models import Edicao


def _dia(data):
    try:
        return date.fromisoformat(data)
    except ValueError:
        raise Http404("Data inválida.")


def _edicao(data, turno):
    if turno not in Edicao.Turno.values:
        raise Http404("Turno inválido.")
    return get_object_or_404(Edicao, data_edicao=_dia(data), turno=turno)


def _arquivo(campo, **kwargs):
    if not campo:
        raise Http404("Arquivo ainda não gerado.")
    try:
        return FileResponse(campo.open("rb"), **kwargs)
    except FileNotFoundError:
        raise Http404("Arquivo não encontrado no disco.")


@require_GET
def edicao_pdf(request, data, turno):
    edicao = _edicao(data, turno)
    return _arquivo(edicao.arquivo_pdf, content_type="application/pdf",
                    filename=f"expresso-pb-{edicao.data_edicao}-{edicao.turno}.pdf")


@require_GET
def edicao_download(request, data, turno):
    edicao = _edicao(data, turno)
    return _arquivo(edicao.arquivo_pdf, as_attachment=True, content_type="application/pdf",
                    filename=f"expresso-pb-{edicao.data_edicao}-{edicao.turno}.pdf")


@require_GET
def edicao_capa(request, data, turno):
    edicao = _edicao(data, turno)
    return _arquivo(edicao.capa, content_type="image/png")


@require_GET
def edicao_sem_turno(request, data, destino):
    """Compatibilidade com as URLs de antes das duas edições por dia."""
    edicao = Edicao.objects.filter(data_edicao=_dia(data)).first()  # a mais recente do dia
    if edicao is None:
        raise Http404("Nenhuma edição nesta data.")
    return redirect(f"news:edicao_{destino}", data=data, turno=edicao.turno)
