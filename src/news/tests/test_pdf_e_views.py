import unittest
from datetime import date
from io import StringIO
from unittest import mock

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.urls import reverse

from news.models import Edicao
from news.services.montagem import montar_edicao
from news.services.pdf_generator import gerar_pdf_da_edicao, renderizar_html

from .base import DIA_FIXTURES, FIXTURES, ParaipythonTestCase

try:
    import weasyprint  # noqa: F401
    TEM_WEASYPRINT = True
except (ImportError, OSError):  # OSError: faltam libs nativas (pango) no sistema
    TEM_WEASYPRINT = False


class TemplatePdfTest(ParaipythonTestCase):
    def test_html_tem_manchete_referencias_e_expediente(self):
        self.carregar_feeds()
        html = renderizar_html(montar_edicao(DIA_FIXTURES))
        self.assertIn("Mulher mata ex", html)
        self.assertNotIn("data:image/svg+xml", html)  # sem QR codes
        self.assertIn("Referências", html)
        self.assertIn("[1]", html)
        # pauta repetida: a referência traz o link do outro portal também
        self.assertIn("https://g1.globo.com/pb/paraiba/noticia/2026/11/15/mulher-mata-ex", html)
        self.assertIn("https://jornaldaparaiba.com.br/cotidiano/mulher-mata-ex", html)
        self.assertIn("Expediente", html)
        self.assertIn("domingo, 15 de novembro de 2026", html.lower())


@unittest.skipUnless(TEM_WEASYPRINT, "WeasyPrint indisponível neste ambiente")
class GerarPdfTest(ParaipythonTestCase):
    def test_gera_pdf_e_capa(self):
        self.carregar_feeds()
        edicao = gerar_pdf_da_edicao(montar_edicao(DIA_FIXTURES))
        with edicao.arquivo_pdf.open("rb") as f:
            self.assertEqual(f.read(4), b"%PDF")
        self.assertTrue(edicao.arquivo_pdf.name.endswith("expresso-pb-2026-11-15.pdf"))
        self.assertTrue(edicao.capa)

    def test_comando_completo_com_feeds_locais(self):
        saida = StringIO()
        call_command(
            "fetch_daily_news", "--data", DIA_FIXTURES.isoformat(),
            "--feed-local", f"g1 PB={FIXTURES / 'g1_pb.xml'}",
            "--feed-local", f"Jornal da Paraíba={FIXTURES / 'jornal_da_paraiba.xml'}",
            stdout=saida,
        )
        self.assertIn("PDF salvo", saida.getvalue())
        self.assertTrue(Edicao.objects.get(data_edicao=DIA_FIXTURES).arquivo_pdf)


class ViewsTest(ParaipythonTestCase):
    def test_home_vazia(self):
        resp = self.client.get(reverse("news:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ainda tá passando")

    def test_home_com_edicao_de_hoje(self):
        self.carregar_feeds()
        edicao = montar_edicao(DIA_FIXTURES)
        edicao.arquivo_pdf.save("teste.pdf", ContentFile(b"%PDF-1.7"), save=True)
        with mock.patch("news.views.public.timezone.localdate", return_value=DIA_FIXTURES):
            resp = self.client.get(reverse("news:home"))
        self.assertContains(resp, "O Expresso de Hoje Saiu Quentinho")
        self.assertContains(resp, edicao.get_download_url())
        self.assertContains(resp, "Nesta xícara")

    def test_home_mostra_ultima_edicao_quando_hoje_nao_saiu(self):
        self.carregar_feeds()
        edicao = montar_edicao(DIA_FIXTURES)
        edicao.arquivo_pdf.name = "edicoes_pdf/qualquer.pdf"
        edicao.save()
        with mock.patch("news.views.public.timezone.localdate", return_value=date(2026, 11, 20)):
            resp = self.client.get(reverse("news:home"))
        self.assertContains(resp, "Baixar Última Edição Disponível (15/11/2026)")

    def test_pdf_inexistente_da_404(self):
        self.assertEqual(self.client.get("/edicao/2020-01-01/pdf/").status_code, 404)
        self.assertEqual(self.client.get("/edicao/nao-e-data/pdf/").status_code, 404)

    def test_acervo_e_sobre(self):
        self.assertContains(self.client.get(reverse("news:acervo")), "acervo ainda está vazio")
        self.assertContains(self.client.get(reverse("web:sobre")), "Jornal da Paraíba")
