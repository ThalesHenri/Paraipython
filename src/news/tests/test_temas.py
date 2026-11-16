from django.test import SimpleTestCase

from news.services.temas import classificar
from news.temas import Tema


class ClassificarTest(SimpleTestCase):
    """Títulos reais do feed do G1 PB e do Jornal da Paraíba."""

    def assertTema(self, titulo, tema, resumo="", categoria="", link=""):
        self.assertEqual(classificar(titulo, resumo, categoria, link), tema, titulo)

    def test_policia(self):
        self.assertTema("Homem atira em irmão após desentendimento familiar, em João Pessoa", Tema.POLICIA)
        self.assertTema("Casa lotérica dentro de supermercado é alvo de assalto em Campina Grande", Tema.POLICIA)

    def test_educacao(self):
        self.assertTema("Servidor público aposentado faz Enem 2026 para tentar nova carreira", Tema.EDUCACAO)

    def test_clima(self):
        self.assertTema("Inmet emite alerta de chuvas intensas para mais de 30 cidades da PB", Tema.CLIMA)

    def test_economia(self):
        self.assertTema("PIB da Paraíba foi o que mais cresceu entre todos os estados, aponta IBGE", Tema.ECONOMIA)
        self.assertTema("Concurso da prefeitura de Natuba tem mais de 140 vagas", Tema.ECONOMIA)

    def test_cultura(self):
        self.assertTema("Fábio Júnior, José Augusto e mais: veja a agenda cultural do fim de semana", Tema.CULTURA)

    def test_politica(self):
        self.assertTema("ALPB derruba decisão sobre tornozeleira do deputado", Tema.POLITICA)

    def test_categoria_do_portal_ajuda(self):
        self.assertTema("Belo vence o clássico no Almeidão", Tema.ESPORTES, categoria="Esportes")

    def test_sem_palavra_chave_vai_para_cidade(self):
        self.assertTema("Rompimento de tubulação provoca falta de água em bairro de João Pessoa", Tema.CIDADE)

    def test_palavra_inteira_nao_casa_pedaco(self):
        # "mar" não pode casar com "marido"
        self.assertNotEqual(classificar("Influenciador e o marido são transferidos"), Tema.CLIMA)
