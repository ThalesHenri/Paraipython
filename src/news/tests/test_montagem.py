from datetime import date, timedelta

from django.test import override_settings

from news.models import Edicao, Noticia
from news.services.montagem import (
    distribuir_por_tema, fim_da_janela, montar_edicao, similaridade, turno_atual,
)
from news.temas import ORDEM_TEMAS

from .base import DIA_FIXTURES, ParaipythonTestCase, as_horas, montar


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


class TurnosTest(ParaipythonTestCase):
    def test_turno_pelo_horario(self):
        self.assertEqual(turno_atual(as_horas(DIA_FIXTURES, 6)), Edicao.Turno.MANHA)
        self.assertEqual(turno_atual(as_horas(DIA_FIXTURES, 19)), Edicao.Turno.NOITE)

    def test_janela_nao_passa_de_2h_depois_do_horario_oficial(self):
        # Refazer a edição da manhã às 15h não pode puxar notícias da tarde.
        fim = fim_da_janela(DIA_FIXTURES, "manha", agora=as_horas(DIA_FIXTURES, 15))
        self.assertEqual(fim, as_horas(DIA_FIXTURES, 8))

    @override_settings(PARAIPYTHON={**__import__("django.conf").conf.settings.PARAIPYTHON,
                                    "HORARIO_NOITE": "19:30"})
    def test_horario_configuravel(self):
        fim = fim_da_janela(DIA_FIXTURES, "noite", agora=as_horas(DIA_FIXTURES, 23))
        self.assertEqual(fim, as_horas(DIA_FIXTURES, 21, 30))


class MontarEdicaoTest(ParaipythonTestCase):
    def setUp(self):
        super().setUp()
        self.carregar_feeds()

    def rels(self, edicao):
        return list(edicao.edicaonoticia_set.select_related("noticia").order_by("posicao"))

    def test_pauta_repercutida_vira_manchete(self):
        rels = self.rels(montar())
        self.assertIn("Mulher mata ex", rels[0].noticia.titulo)
        self.assertEqual(rels[0].outros_links[0]["fonte"], "g1 PB")
        self.assertIn("g1.globo.com", rels[0].outros_links[0]["link"])

    def test_nao_repete_a_mesma_pauta_na_edicao(self):
        titulos = [n.titulo for n in montar().noticias.all()]
        self.assertEqual(sum("Mulher mata ex" in t for t in titulos), 1)

    def test_secoes_na_ordem_do_jornal(self):
        temas = [r.tema for r in self.rels(montar())[1:]]  # sem a manchete
        self.assertEqual(temas, sorted(temas, key=ORDEM_TEMAS.index))

    @override_settings(PARAIPYTHON={**__import__("django.conf").conf.settings.PARAIPYTHON,
                                    "MAX_POR_TEMA": 2})
    def test_teto_por_tema(self):
        temas = [r.tema for r in self.rels(montar())[1:]]
        for tema in set(temas):
            self.assertLessEqual(temas.count(tema), 2)

    def test_limite_de_noticias(self):
        self.assertEqual(montar(limite=5).noticias.count(), 5)

    def test_noticia_antiga_fica_de_fora(self):
        self.assertFalse(montar().noticias.filter(titulo__icontains="Festival de inverno").exists())

    def test_refazer_mantem_numero_e_edicao(self):
        primeira = montar()
        segunda = montar()
        self.assertEqual(primeira.pk, segunda.pk)
        self.assertEqual(Edicao.objects.count(), 1)

    def test_sem_noticias_nao_cria_edicao(self):
        self.assertIsNone(montar(dia=date(2020, 1, 1)))


class SemRepetecoTest(ParaipythonTestCase):
    """Manhã e noite do mesmo dia não podem repetir notícia."""

    def setUp(self):
        super().setUp()
        self.carregar_feeds()
        self.manha = montar(turno="manha", hora=6)
        self.noite = montar(turno="noite", hora=19)

    def test_duas_edicoes_no_mesmo_dia_com_numeracao_corrida(self):
        self.assertEqual((self.manha.numero_edicao, self.noite.numero_edicao), (1, 2))

    def test_noite_comeca_onde_a_manha_parou(self):
        corte = self.manha.fim_janela
        for noticia in self.noite.noticias.all():
            self.assertGreater(noticia.publicado_em, corte)

    def test_nenhuma_noticia_repetida(self):
        ids_manha = set(self.manha.noticias.values_list("pk", flat=True))
        ids_noite = set(self.noite.noticias.values_list("pk", flat=True))
        self.assertFalse(ids_manha & ids_noite)

    def test_mesma_pauta_com_link_novo_nao_volta(self):
        # O portal republica a manchete da manhã à tarde, com outro endereço.
        original = self.manha.edicaonoticia_set.get(posicao=0).noticia
        Noticia.objects.create(
            titulo=original.titulo + " (atualizada)",
            link=original.link + "?atualizacao=1",
            resumo="Nova versão da mesma história.",
            publicado_em=as_horas(DIA_FIXTURES, 17),
            fonte=original.fonte,
            tema=original.tema,
        )
        noite = montar(turno="noite", hora=19)
        self.assertFalse(noite.noticias.filter(link__endswith="?atualizacao=1").exists())

    def test_dia_seguinte_sem_novidades_nao_publica(self):
        self.assertIsNone(montar(dia=DIA_FIXTURES + timedelta(days=1), turno="manha", hora=6))


class DistribuirPorTemaTest(ParaipythonTestCase):
    def test_rotina_nao_vira_manchete(self):
        self.carregar_feeds()
        Noticia.objects.create(
            titulo="Previsão do tempo hoje para João Pessoa (PB): sol com nuvens",
            link="https://exemplo.com/previsao", resumo="Sol.", tema="clima",
            publicado_em=as_horas(DIA_FIXTURES, 18, 50), fonte=self.g1,
        )
        manchete = montar().edicaonoticia_set.get(posicao=0).noticia
        self.assertNotIn("Previsão do tempo", manchete.titulo)

    def test_lista_vazia(self):
        self.assertEqual(distribuir_por_tema([], 16, 4), [])

    def test_montar_edicao_sem_turno_usa_o_horario(self):
        self.carregar_feeds()
        edicao = montar_edicao(DIA_FIXTURES, agora=as_horas(DIA_FIXTURES, 19))
        self.assertEqual(edicao.turno, Edicao.Turno.NOITE)
