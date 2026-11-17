import unittest
from datetime import date
from io import StringIO
from unittest import mock

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.urls import reverse

from news.models import Edicao
from news.services.pdf_generator import gerar_pdf_da_edicao, renderizar_html

from .base import DIA_FIXTURES, FIXTURES, ParaipythonTestCase, montar

try:
    import weasyprint  # noqa: F401
    TEM_WEASYPRINT = True
except (ImportError, OSError):  # OSError: faltam libs nativas (pango) no sistema
    TEM_WEASYPRINT = False


class TemplatePdfTest(ParaipythonTestCase):
    def test_html_tem_manchete_referencias_e_expediente(self):
        self.carregar_feeds()
        html = renderizar_html(montar())
        self.assertIn("Mulher mata ex", html)
        self.assertNotIn("data:image/svg+xml", html)  # sem QR codes
        self.assertIn("Referências", html)
        self.assertIn("[1]", html)
        # pauta repetida: a referência traz o link do outro portal também
        self.assertIn("https://g1.globo.com/pb/paraiba/noticia/2026/11/15/mulher-mata-ex", html)
        self.assertIn("https://jornaldaparaiba.com.br/cotidiano/mulher-mata-ex", html)
        self.assertIn("Expediente", html)
        self.assertIn("domingo, 15 de novembro de 2026", html.lower())

    def test_html_tem_secoes_sumario_e_cabecalho_noturno(self):
        self.carregar_feeds()
        html = renderizar_html(montar())
        self.assertIn('class="sumario"', html)
        self.assertIn('href="#secao-policia"', html)
        self.assertIn('id="secao-educacao"', html)
        self.assertIn("Edição Noturna", html)
        self.assertIn("img/xicara-noite.svg", html)

    def test_cabecalho_da_manha(self):
        self.carregar_feeds()
        html = renderizar_html(montar(turno="manha", hora=6))
        self.assertIn("Edição da Manhã", html)
        self.assertIn("img/xicara.svg", html)
        self.assertIn("Edição forte", html)


@unittest.skipUnless(TEM_WEASYPRINT, "WeasyPrint indisponível neste ambiente")
def links_do_pdf(caminho):
    """Lê as anotações de link do PDF: (URLs externas, páginas de destino internas, marcadores)."""
    import ctypes

    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    pdf = pdfium.PdfDocument(caminho)
    externos, internos = set(), set()
    for indice in range(len(pdf)):
        pagina, posicao = pdf[indice], 0
        while True:
            link, pos = raw.FPDF_LINK(), ctypes.c_int(posicao)
            if not raw.FPDFLink_Enumerate(pagina.raw, ctypes.byref(pos), ctypes.byref(link)):
                break
            posicao = pos.value
            acao = raw.FPDFLink_GetAction(link)
            destino = raw.FPDFLink_GetDest(pdf.raw, link)
            if acao:
                tamanho = raw.FPDFAction_GetURIPath(pdf.raw, acao, None, 0)
                if tamanho:
                    buffer = ctypes.create_string_buffer(tamanho)
                    raw.FPDFAction_GetURIPath(pdf.raw, acao, buffer, tamanho)
                    externos.add(buffer.value.decode())
                    continue
                destino = raw.FPDFAction_GetDest(pdf.raw, acao) or destino
            if destino:
                internos.add((indice + 1, raw.FPDFDest_GetDestPageIndex(pdf.raw, destino) + 1))
    marcadores = [m.get_title() for m in pdf.get_toc()]
    pdf.close()
    return externos, internos, marcadores


class GerarPdfTest(ParaipythonTestCase):
    def test_gera_pdf_e_capa(self):
        self.carregar_feeds()
        edicao = gerar_pdf_da_edicao(montar())
        with edicao.arquivo_pdf.open("rb") as f:
            self.assertEqual(f.read(4), b"%PDF")
        self.assertTrue(edicao.arquivo_pdf.name.endswith("expresso-pb-2026-11-15-noite.pdf"))
        self.assertTrue(edicao.capa)

    def test_links_clicaveis_e_marcadores(self):
        self.carregar_feeds()
        edicao = gerar_pdf_da_edicao(montar())
        externos, internos, marcadores = links_do_pdf(edicao.arquivo_pdf.path)

        # Todo link de matéria (e do outro portal, na pauta repetida) está clicável.
        for rel in edicao.edicaonoticia_set.select_related("noticia"):
            self.assertIn(rel.noticia.link, externos)
            for outro in rel.outros_links:
                self.assertIn(outro["link"], externos)

        # Há links internos: [n] → Referências, Referências → notícia, sumário → seções.
        self.assertTrue(internos)
        ultima = max(destino for _, destino in internos)
        self.assertTrue(any(origem == 1 and destino > 1 for origem, destino in internos))  # capa → adiante
        self.assertIn((1, 1), internos)  # sumário → seção que começa na própria capa
        self.assertTrue(any(origem == ultima and destino < ultima for origem, destino in internos))  # volta

        # Painel lateral: manchete, temas e Referências — sem o título de cada notícia.
        self.assertTrue(marcadores[0].startswith("Manchete: "))
        self.assertEqual(marcadores[-1], "Referências")
        self.assertIn("Polícia", marcadores)
        segunda = edicao.edicaonoticia_set.get(posicao=1).noticia.titulo
        self.assertNotIn(segunda, marcadores)

    def test_comando_completo_com_feeds_locais(self):
        saida = StringIO()
        call_command(
            "fetch_daily_news", "--data", DIA_FIXTURES.isoformat(), "--turno", "noite",
            "--feed-local", f"g1 PB={FIXTURES / 'g1_pb.xml'}",
            "--feed-local", f"Jornal da Paraíba={FIXTURES / 'jornal_da_paraiba.xml'}",
            stdout=saida,
        )
        self.assertIn("PDF salvo", saida.getvalue())
        self.assertTrue(Edicao.objects.get(data_edicao=DIA_FIXTURES, turno="noite").arquivo_pdf)


class ViewsTest(ParaipythonTestCase):
    def test_home_vazia(self):
        resp = self.client.get(reverse("news:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ainda tá passando")

    def test_home_com_edicao_de_hoje(self):
        self.carregar_feeds()
        edicao = montar(turno="manha", hora=6)
        edicao.arquivo_pdf.save("teste.pdf", ContentFile(b"%PDF-1.7"), save=True)
        with mock.patch("news.views.public.timezone.localdate", return_value=DIA_FIXTURES):
            resp = self.client.get(reverse("news:home"))
        self.assertContains(resp, "O Expresso de Hoje Saiu Quentinho")
        self.assertContains(resp, edicao.get_download_url())
        self.assertContains(resp, "Nesta xícara")

    def test_home_mostra_ultima_edicao_quando_hoje_nao_saiu(self):
        self.carregar_feeds()
        edicao = montar()
        edicao.arquivo_pdf.name = "edicoes_pdf/qualquer.pdf"
        edicao.save()
        with mock.patch("news.views.public.timezone.localdate", return_value=date(2026, 11, 20)):
            resp = self.client.get(reverse("news:home"))
        self.assertContains(resp, "Baixar Última Edição Disponível (Edição Noturna, 15/11/2026)")

    def test_pdf_inexistente_da_404(self):
        self.assertEqual(self.client.get("/edicao/2020-01-01/manha/pdf/").status_code, 404)
        self.assertEqual(self.client.get("/edicao/nao-e-data/manha/pdf/").status_code, 404)
        self.assertEqual(self.client.get("/edicao/2020-01-01/pdf/").status_code, 404)

    def test_turno_invalido_da_404(self):
        self.carregar_feeds()
        montar()
        self.assertEqual(self.client.get("/edicao/2026-11-15/tarde/pdf/").status_code, 404)

    def test_url_antiga_redireciona_para_a_edicao_mais_recente_do_dia(self):
        self.carregar_feeds()
        montar(turno="manha", hora=6)
        montar(turno="noite", hora=19)
        resp = self.client.get("/edicao/2026-11-15/download/")
        self.assertRedirects(resp, "/edicao/2026-11-15/noite/download/", fetch_redirect_response=False)

    def test_home_noturna_oferece_a_da_manha(self):
        self.carregar_feeds()
        for turno, hora in (("manha", 6), ("noite", 19)):
            edicao = montar(turno=turno, hora=hora)
            edicao.arquivo_pdf.save(f"{turno}.pdf", ContentFile(b"%PDF-1.7"), save=True)
        with mock.patch("news.views.public.timezone.localdate", return_value=DIA_FIXTURES):
            resp = self.client.get(reverse("news:home"))
        self.assertContains(resp, "A Edição Noturna Chegou")
        self.assertContains(resp, "Perdeu a Edição da Manhã?")

    def test_acervo_agrupa_por_dia(self):
        self.carregar_feeds()
        for turno, hora in (("manha", 6), ("noite", 19)):
            edicao = montar(turno=turno, hora=hora)
            edicao.arquivo_pdf.save(f"{turno}.pdf", ContentFile(b"%PDF-1.7"), save=True)
        resp = self.client.get(reverse("news:acervo"))
        self.assertContains(resp, "2 edições")
        self.assertContains(resp, "Domingo, 15 de")
        html = resp.content.decode()
        self.assertLess(html.index("Edição da Manhã"), html.index("Edição Noturna"))

    def test_acervo_e_sobre(self):
        self.assertContains(self.client.get(reverse("news:acervo")), "acervo ainda está vazio")
        self.assertContains(self.client.get(reverse("web:sobre")), "Jornal da Paraíba")
