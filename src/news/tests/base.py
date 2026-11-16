import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path

from django.test import TestCase, override_settings
from django.utils import timezone

from news.models import FonteNoticia
from news.services.coleta import coletar_fonte
from news.services.montagem import montar_edicao

FIXTURES = Path(__file__).parent / "fixtures"
DIA_FIXTURES = date(2026, 11, 15)  # data das notícias dos feeds de exemplo


def ler_fixture(nome):
    return (FIXTURES / nome).read_bytes()


def as_horas(dia, hora, minuto=0):
    """Momento em horário de João Pessoa (o robô "roda" nesse instante)."""
    return timezone.make_aware(datetime(dia.year, dia.month, dia.day, hora, minuto))


def montar(dia=DIA_FIXTURES, turno="noite", hora=19, **kwargs):
    """Monta a edição como se o cron tivesse rodado no horário dado."""
    return montar_edicao(dia, turno, agora=as_horas(dia, hora), **kwargs)


class ParaipythonTestCase(TestCase):
    """Base: MEDIA_ROOT temporário e atalhos para carregar os feeds de exemplo."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix="paraipython-media-")
        cls._override = override_settings(MEDIA_ROOT=cls._media)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)

    def setUp(self):
        # As fontes vêm da migration 0002_fontes_iniciais.
        self.g1 = FonteNoticia.objects.get(nome="g1 PB")
        self.jpb = FonteNoticia.objects.get(nome="Jornal da Paraíba")

    def carregar_feeds(self):
        coletar_fonte(self.g1, ler_fixture("g1_pb.xml"))
        coletar_fonte(self.jpb, ler_fixture("jornal_da_paraiba.xml"))
