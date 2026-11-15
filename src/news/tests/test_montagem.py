from datetime import date

from news.models import Edicao
from news.services.montagem import montar_edicao, similaridade

from .base import DIA_FIXTURES, ParaipythonTestCase


class SimilaridadeTest(ParaipythonTestCase):
    def test_mesma_pauta_em_portais_diferentes(self):
        self.assertGreaterEqual(similaridade(
            "Mulher mata ex com golpe de faca, em João Pessoa, e alega legítima defesa",
            "Mulher mata ex com golpe de faca e alega legítima defesa, em João Pessoa",
        ), 0.9)
        self.assertGreaterEqual(similaridade(
            "Inmet emite alerta de chuvas intensas para mais de 30 cidades da PB",
            "Chuvas intensas: Inmet emite alerta para 32 cidades na Paraíba",
        ), 0.6)

    def test_pautas_diferentes(self):
        self.assertLess(similaridade(
            "Homem é encontrado morto em fazenda, na Grande João Pessoa",
            "Homem atira em irmão após desentendimento familiar, em João Pessoa",
        ), 0.6)
        self.assertLess(similaridade(
            "Servidor público aposentado faz Enem 2026 para tentar nova carreira, na Paraíba",
            "Professor de história faz Enem pela quinta vez para tentar vaga em geografia",
        ), 0.6)


class MontarEdicaoTest(ParaipythonTestCase):
    def setUp(self):
        super().setUp()
        self.carregar_feeds()

    def test_pautas_repercutidas_abrem_a_edicao(self):
        edicao = montar_edicao(DIA_FIXTURES)
        rels = list(edicao.edicaonoticia_set.order_by("posicao"))
        self.assertIn("Mulher mata ex", rels[0].noticia.titulo)
        self.assertTrue(rels[0].outras_fontes)
        self.assertEqual(rels[0].outros_links[0]["fonte"], "g1 PB")
        self.assertIn("g1.globo.com", rels[0].outros_links[0]["link"])
        self.assertIn("Inmet", rels[1].noticia.titulo)

    def test_nao_repete_a_mesma_pauta(self):
        edicao = montar_edicao(DIA_FIXTURES)
        titulos = [n.titulo for n in edicao.noticias.all()]
        self.assertEqual(sum("Mulher mata ex" in t for t in titulos), 1)

    def test_noticia_antiga_fica_de_fora(self):
        edicao = montar_edicao(DIA_FIXTURES)
        self.assertFalse(edicao.noticias.filter(titulo__icontains="Festival de inverno").exists())

    def test_limite_de_noticias(self):
        edicao = montar_edicao(DIA_FIXTURES, limite=5)
        self.assertEqual(edicao.noticias.count(), 5)

    def test_refazer_mantem_numero(self):
        primeira = montar_edicao(DIA_FIXTURES)
        segunda = montar_edicao(DIA_FIXTURES)
        self.assertEqual(primeira.pk, segunda.pk)
        self.assertEqual(Edicao.objects.count(), 1)
        self.assertEqual(segunda.numero_edicao, 1)

    def test_numeracao_sequencial(self):
        montar_edicao(DIA_FIXTURES)
        Edicao.objects.create(data_edicao=date(2026, 11, 16), numero_edicao=Edicao.proximo_numero())
        self.assertEqual(Edicao.objects.get(data_edicao=date(2026, 11, 16)).numero_edicao, 2)

    def test_sem_noticias_nao_cria_edicao(self):
        self.assertIsNone(montar_edicao(date(2020, 1, 1)))
