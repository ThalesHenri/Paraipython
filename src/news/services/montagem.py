"""Montagem da edição do dia: escolhe as notícias, remove pautas repetidas e ordena.

Critério de relevância (simples e explicável):
1. Pauta que saiu em mais de um portal vale mais (se G1 e Jornal da Paraíba deram,
   é assunto do dia). A mais repercutida vira a manchete.
2. O resto entra alternando os portais, do mais recente para o mais antigo, para a
   edição não virar "o G1 impresso".
"""
import re
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from news.models import Edicao, EdicaoNoticia, Noticia

PALAVRAS_VAZIAS = set(
    """
    a o as os um uma uns umas de do da dos das em no na nos nas por pelo pela pelos pelas
    para pra com sem sob sobre e ou que se ao aos à às é foi ser são após apos ate até mais
    menos como já ja seu sua seus suas ele ela eles elas isso essa esse este esta neste nesta
    veja diz dizem joao joão pessoa paraiba paraíba pb grande
    """.split()
)


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def palavras_chave(titulo):
    texto = _sem_acento(titulo.lower())
    tokens = re.findall(r"[a-z0-9]+", texto)
    return {t for t in tokens if len(t) > 2 and t not in PALAVRAS_VAZIAS}


def similaridade(titulo_a, titulo_b):
    """Coeficiente de sobreposição entre as palavras-chave dos dois títulos (0 a 1)."""
    a, b = palavras_chave(titulo_a), palavras_chave(titulo_b)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


@dataclass
class Pauta:
    """Um assunto, com todas as notícias (de portais diferentes) que falam dele."""

    noticias: list = field(default_factory=list)

    @property
    def fontes(self):
        return list(OrderedDict.fromkeys(n.fonte.nome for n in self.noticias))

    @property
    def principal(self):
        # A versão com o resumo mais completo representa a pauta.
        return max(self.noticias, key=lambda n: (len(n.resumo), n.publicado_em))

    @property
    def mais_recente(self):
        return max(n.publicado_em for n in self.noticias)


def agrupar_pautas(noticias, limiar=None):
    limiar = limiar if limiar is not None else settings.PARAIPYTHON["LIMIAR_DUPLICADA"]
    pautas = []
    for noticia in noticias:
        for pauta in pautas:
            if any(similaridade(noticia.titulo, n.titulo) >= limiar for n in pauta.noticias):
                pauta.noticias.append(noticia)
                break
        else:
            pautas.append(Pauta(noticias=[noticia]))
    return pautas


def ordenar_pautas(pautas):
    repercutidas = sorted(
        (p for p in pautas if len(p.fontes) > 1),
        key=lambda p: (len(p.fontes), p.mais_recente),
        reverse=True,
    )
    # Pautas de um portal só: alterna entre os portais, mais recentes primeiro.
    por_fonte = OrderedDict()
    for pauta in sorted((p for p in pautas if len(p.fontes) == 1), key=lambda p: p.mais_recente, reverse=True):
        por_fonte.setdefault(pauta.fontes[0], []).append(pauta)
    intercaladas = []
    filas = list(por_fonte.values())
    while any(filas):
        for fila in filas:
            if fila:
                intercaladas.append(fila.pop(0))
    return repercutidas + intercaladas


def links_de_outros_portais(pauta):
    """Um link por portal (além do principal), para a seção de Referências do PDF."""
    principal = pauta.principal
    vistos, links = {principal.fonte.nome}, []
    for noticia in sorted(pauta.noticias, key=lambda n: n.publicado_em, reverse=True):
        if noticia.fonte.nome not in vistos:
            vistos.add(noticia.fonte.nome)
            links.append({"fonte": noticia.fonte.nome, "link": noticia.link})
    return links


def referencia_da_data(data):
    """Momento de corte da edição: agora (edição de hoje) ou o fim do dia (edição passada)."""
    agora = timezone.now()
    if data >= timezone.localdate():
        return agora
    fim_do_dia = datetime.combine(data, dt_time(23, 59, 59))
    return timezone.make_aware(fim_do_dia)


def selecionar_pautas(data, limite=None, janela_horas=None):
    cfg = settings.PARAIPYTHON
    limite = limite or cfg["NOTICIAS_POR_EDICAO"]
    janela_horas = janela_horas or cfg["JANELA_HORAS"]
    fim = referencia_da_data(data)
    inicio = fim - timedelta(hours=janela_horas)
    noticias = (
        Noticia.objects.filter(publicado_em__gt=inicio, publicado_em__lte=fim, fonte__ativa=True)
        .select_related("fonte")
        .order_by("-publicado_em")
    )
    return ordenar_pautas(agrupar_pautas(list(noticias)))[:limite]


@transaction.atomic
def montar_edicao(data=None, limite=None):
    """Cria (ou refaz) a edição da data com as notícias selecionadas.

    Retorna a edição, ou ``None`` se não houver nenhuma notícia na janela.
    """
    data = data or timezone.localdate()
    pautas = selecionar_pautas(data, limite=limite)
    if not pautas:
        return None

    edicao = Edicao.objects.filter(data_edicao=data).first()
    if edicao is None:
        edicao = Edicao.objects.create(data_edicao=data, numero_edicao=Edicao.proximo_numero())
    EdicaoNoticia.objects.filter(edicao=edicao).delete()

    EdicaoNoticia.objects.bulk_create(
        [
            EdicaoNoticia(
                edicao=edicao,
                noticia=pauta.principal,
                posicao=posicao,
                outras_fontes=", ".join(f for f in pauta.fontes if f != pauta.principal.fonte.nome),
                outros_links=links_de_outros_portais(pauta),
            )
            for posicao, pauta in enumerate(pautas)
        ]
    )
    return edicao
