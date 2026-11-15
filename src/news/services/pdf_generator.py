"""Renderiza a edição em HTML/CSS e converte para PDF com o WeasyPrint.

As fontes ficam em ``static/fonts`` e são carregadas do disco (``base_url``), então o
PDF sai igual em qualquer servidor, sem depender do Google Fonts.
"""
import io
import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone, translation

from news.models import Edicao

logger = logging.getLogger(__name__)

PASTA_STATIC = settings.BASE_DIR / "static"


def romano(numero):
    valores = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
               (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    saida = ""
    for valor, letra in valores:
        while numero >= valor:
            saida += letra
            numero -= valor
    return saida


def montar_contexto(edicao):
    itens = []
    relacoes = edicao.edicaonoticia_set.select_related("noticia__fonte").order_by("posicao")
    for numero, rel in enumerate(relacoes, start=1):
        itens.append(
            {
                "ref": numero,  # número da notícia na seção de Referências
                "noticia": rel.noticia,
                "outras_fontes": rel.outras_fontes,
                "outros_links": rel.outros_links,
            }
        )
    fontes = sorted({i["noticia"].fonte.nome for i in itens})
    return {
        "edicao": edicao,
        "manchete": itens[0] if itens else None,
        "demais": itens[1:],
        "referencias": itens,
        "fontes": fontes,
        "gerado_em": timezone.localtime(),
        "anno": romano(max(edicao.data_edicao.year - 2025, 1)),  # o Expresso PB nasceu em 2026: Anno I
    }


def renderizar_html(edicao):
    with translation.override("pt-br"):
        return render_to_string("pdf/jornal_template.html", montar_contexto(edicao))


def renderizar_pdf(edicao):
    from weasyprint import HTML  # import tardio: o site funciona mesmo sem o WeasyPrint

    html = renderizar_html(edicao)
    return HTML(string=html, base_url=str(PASTA_STATIC)).write_pdf()


def gerar_capa_png(pdf_bytes, largura=900):
    """Miniatura da 1ª página (para a home). Opcional: precisa do pypdfium2."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        logger.info("pypdfium2 não instalado: edição sem miniatura da capa.")
        return None
    pdf = pdfium.PdfDocument(pdf_bytes)
    pagina = pdf[0]
    escala = largura / pagina.get_width()
    imagem = pagina.render(scale=escala).to_pil()
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG", optimize=True)
    pdf.close()
    return buffer.getvalue()


def _salvar_sobrescrevendo(campo, nome, conteudo):
    """Salva sempre com o mesmo nome (expresso-pb-AAAA-MM-DD.pdf).

    Sem isso, ao refazer a edição o Django criaria "expresso-pb-...-aB3xYz.pdf".
    """
    if campo:
        campo.delete(save=False)
    destino = campo.field.generate_filename(campo.instance, nome)
    if campo.storage.exists(destino):
        campo.storage.delete(destino)
    campo.save(nome, ContentFile(conteudo), save=False)


def gerar_pdf_da_edicao(edicao: Edicao):
    """Gera o PDF (e a miniatura) e grava nos campos da edição."""
    pdf_bytes = renderizar_pdf(edicao)
    nome_base = f"expresso-pb-{edicao.data_edicao.isoformat()}"

    _salvar_sobrescrevendo(edicao.arquivo_pdf, f"{nome_base}.pdf", pdf_bytes)
    capa = gerar_capa_png(pdf_bytes)
    if capa:
        _salvar_sobrescrevendo(edicao.capa, f"{nome_base}.png", capa)

    edicao.save()
    logger.info("PDF gerado: %s (%.0f KB)", edicao.arquivo_pdf.name, len(pdf_bytes) / 1024)
    return edicao
