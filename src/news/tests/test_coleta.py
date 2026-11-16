from datetime import datetime, timezone as dt_timezone
from unittest import mock

import requests

from news.models import FonteNoticia, Noticia
from news.services.coleta import (
    coletar_fonte, dividir_frases, extrair_itens, melhor_resumo, resumir,
)

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
    def test_dividir_frases_respeita_abreviacoes_e_numeros(self):
        texto = "O Sr. Silva mora na Av. Epitácio. Pagou R$ 1.500 ao dr. J. Souza! Depois saiu."
        self.assertEqual(dividir_frases(texto), [
            "O Sr. Silva mora na Av. Epitácio.", "Pagou R$ 1.500 ao dr. J. Souza!", "Depois saiu.",
        ])

    def test_resumo_junta_frases_inteiras_sem_reticencias(self):
        texto = "Primeira frase curta. " + "Segunda frase " + "longa " * 60 + "fim."
        resumo = resumir(texto, limite=100, teto=150)
        self.assertEqual(resumo, "Primeira frase curta.")

    def test_primeira_frase_longa_usa_o_teto(self):
        frase = "Uma frase " + "comprida " * 40 + "termina aqui."  # ~370 caracteres
        self.assertEqual(resumir(frase + " Outra.", limite=320, teto=450), frase)

    def test_frase_maior_que_o_teto_devolve_none(self):
        self.assertIsNone(resumir("palavra " * 100, limite=50, teto=80))

    def test_fecha_frase_sem_ponto(self):
        self.assertEqual(resumir("Os dois tinham histórico de brigas"), "Os dois tinham histórico de brigas.")

    def test_melhor_resumo_tenta_a_proxima_fonte(self):
        longo = "palavra " * 100
        self.assertEqual(melhor_resumo([longo, "Resumo alternativo"]), "Resumo alternativo.")

    def test_reticencias_so_como_ultimo_recurso(self):
        self.assertTrue(melhor_resumo(["palavra " * 100]).endswith("…"))

    def test_feeds_de_exemplo_sem_reticencias(self):
        for nome in ("g1_pb.xml", "jornal_da_paraiba.xml"):
            for item in extrair_itens(ler_fixture(nome), agora=AGORA):
                self.assertFalse(item["resumo"].endswith("…"), item["resumo"])
                self.assertRegex(item["resumo"], r"[.!?…][\"”’)]*$")

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


class ReprocessarNoticiasTest(ParaipythonTestCase):
    def test_refaz_resumo_com_reticencias_e_tema(self):
        from io import StringIO

        from django.core.management import call_command

        noticia = Noticia.objects.create(
            titulo="Homem é preso suspeito de assalto em João Pessoa",
            link="https://exemplo.com/assalto",
            resumo="A polícia prendeu um homem suspeito de assaltar uma farmácia no bairro…",
            conteudo_bruto="<p>A polícia prendeu um homem suspeito de assaltar uma farmácia no bairro "
                           "dos Bancários. Ele foi levado para a Central de Polícia.</p>",
            publicado_em=AGORA,
            fonte=self.g1,
            tema="cidade",
        )
        call_command("reprocessar_noticias", stdout=StringIO())
        noticia.refresh_from_db()
        self.assertEqual(
            noticia.resumo,
            "A polícia prendeu um homem suspeito de assaltar uma farmácia no bairro dos Bancários. "
            "Ele foi levado para a Central de Polícia.",
        )
        self.assertEqual(noticia.tema, "policia")
