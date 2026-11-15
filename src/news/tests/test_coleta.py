from datetime import datetime, timezone as dt_timezone
from unittest import mock

import requests

from news.models import FonteNoticia, Noticia
from news.services.coleta import coletar_fonte, extrair_itens, resumir

from .base import ParaipythonTestCase, ler_fixture

AGORA = datetime(2026, 11, 15, 22, 0, tzinfo=dt_timezone.utc)  # 19h em João Pessoa


class ExtrairItensG1Test(ParaipythonTestCase):
    def setUp(self):
        super().setUp()
        self.itens = extrair_itens(ler_fixture("g1_pb.xml"), agora=AGORA)

    def test_le_todos_os_itens(self):
        self.assertEqual(len(self.itens), 10)

    def test_resumo_vem_da_linha_fina(self):
        primeiro = self.itens[0]
        self.assertTrue(primeiro["resumo"].startswith("Segundo a Polícia Civil"))
        self.assertNotIn("WhatsApp", primeiro["resumo"])

    def test_categoria_g1_e_descartada(self):
        self.assertEqual(self.itens[0]["categoria"], "")

    def test_data_menos_zero_e_horario_local(self):
        # "Sun, 15 Nov 2026 18:45:24 -0000" no G1 = 18h45 em João Pessoa = 21h45 UTC
        esperado = datetime(2026, 11, 15, 21, 45, 24, tzinfo=dt_timezone.utc)
        self.assertEqual(self.itens[0]["publicado_em"], esperado)


class ExtrairItensJornalDaParaibaTest(ParaipythonTestCase):
    def setUp(self):
        super().setUp()
        self.itens = extrair_itens(ler_fixture("jornal_da_paraiba.xml"), agora=AGORA)

    def test_resumo_ignora_credito_da_foto(self):
        resumo = self.itens[0]["resumo"]
        self.assertTrue(resumo.startswith("Uma mulher de 42 anos"), resumo)
        self.assertNotIn("Flávio Fernandes", resumo)

    def test_categoria_e_data_gmt(self):
        self.assertEqual(self.itens[1]["categoria"], "Meio Ambiente")
        self.assertEqual(self.itens[0]["publicado_em"], datetime(2026, 11, 15, 15, 48, 46, tzinfo=dt_timezone.utc))


class UtilidadesTest(ParaipythonTestCase):
    def test_resumir_corta_sem_quebrar_palavra(self):
        texto = "palavra " * 100
        resumo = resumir(texto.strip(), limite=50)
        self.assertLessEqual(len(resumo), 51)
        self.assertTrue(resumo.endswith("palavra…"))

    def test_data_no_futuro_vira_momento_da_coleta(self):
        xml = b"""<rss version="2.0"><channel><title>x</title><item><title>Teste</title>
        <link>https://exemplo.com/a</link><pubDate>Mon, 01 Jan 2035 10:00:00 GMT</pubDate>
        </item></channel></rss>"""
        self.assertEqual(extrair_itens(xml, agora=AGORA)[0]["publicado_em"], AGORA)

    def test_feed_invalido_gera_erro(self):
        with self.assertRaises(ValueError):
            extrair_itens(b"isso nao e xml nenhum <<<", agora=AGORA)


class ColetarFonteTest(ParaipythonTestCase):
    def test_salva_e_nao_duplica(self):
        r1 = coletar_fonte(self.g1, ler_fixture("g1_pb.xml"))
        r2 = coletar_fonte(self.g1, ler_fixture("g1_pb.xml"))
        self.assertEqual((r1.novas, r1.repetidas), (10, 0))
        self.assertEqual((r2.novas, r2.repetidas), (0, 10))
        self.assertEqual(Noticia.objects.filter(fonte=self.g1).count(), 10)

    def test_falha_de_rede_nao_derruba_o_robo(self):
        with mock.patch("news.services.coleta.requests.get", side_effect=requests.ConnectionError("sem internet")), \
             mock.patch("news.services.coleta.time.sleep"), \
             self.assertLogs("news.services.coleta", level="WARNING"):
            resultado = coletar_fonte(self.g1)
        self.assertFalse(resultado.ok)
        self.assertIn("sem internet", resultado.erros[0])

    def test_fonte_de_scraping_e_ignorada(self):
        pbagora = FonteNoticia.objects.get(nome="PB Agora")
        resultado = coletar_fonte(pbagora, b"<html></html>")
        self.assertEqual(resultado.novas, 0)
        self.assertFalse(resultado.ok)
