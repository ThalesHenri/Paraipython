"""Montagem das edições (manhã e noturna): escolhe as notícias, remove pautas
repetidas, ordena por relevância e agrupa por tema.

Janela de tempo: cada edição pega o que foi publicado desde o corte da edição anterior
(a da manhã pega a noite e a madrugada; a noturna pega o dia).

Critério de relevância (simples e explicável):
1. Pauta que saiu em mais de um portal vale mais (se G1 e Jornal da Paraíba deram,
   é assunto do dia). A mais repercutida vira a manchete.
2. O resto entra alternando os portais, do mais recente para o mais antigo, para a
   edição não virar "o G1 impresso".
3. No máximo N notícias por tema, para uma seção não engolir as outras.

Sem repeteco: fica de fora o que já saiu numa edição anterior, inclusive a mesma
história republicada pelo portal com outro link.
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
from news.temas import ORDEM_TEMAS, Tema

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


# Conteúdo de rotina entra na seção, mas nunca abre o jornal como manchete.
ROTINEIRAS = re.compile(
    r"previs[aã]o do tempo|aprenda a receita|resolva quest|agenda cultural|"
    r"^v[ií]deo[s]?:|^ao vivo|hor[oó]scopo|resultado da (mega|lotof|quina)",
    re.IGNORECASE,
)


def eh_rotineira(pauta):
    return bool(ROTINEIRAS.search(pauta.principal.titulo))


def tema_da_pauta(pauta):
    return pauta.principal.tema or Tema.CIDADE


# ---------------------------------------------------------------------------
# Turnos e janela de tempo
# ---------------------------------------------------------------------------
TOLERANCIA_ATRASO = timedelta(hours=2)


def turno_atual(agora=None):
    """Antes do meio-dia é a Edição da Manhã; depois, a Noturna."""
    agora = timezone.localtime(agora or timezone.now())
    return Edicao.Turno.MANHA if agora.hour < 12 else Edicao.Turno.NOITE


def horario_do_turno(data, turno):
    chave = "HORARIO_MANHA" if turno == Edicao.Turno.MANHA else "HORARIO_NOITE"
    hora, minuto = (int(x) for x in settings.PARAIPYTHON[chave].split(":"))
    return timezone.make_aware(datetime.combine(data, dt_time(hora, minuto)))


def fim_da_janela(data, turno, agora=None):
    """Corte da edição: o momento em que o robô roda, mas nunca mais de 2h depois do
    horário oficial. Assim, refazer a edição da manhã às 15h não puxa notícias da tarde."""
    agora = agora or timezone.now()
    return min(agora, horario_do_turno(data, turno) + TOLERANCIA_ATRASO)


def inicio_da_janela(data, turno, fim):
    """A janela começa onde a edição anterior parou (com teto, caso o robô falhe um dia)."""
    cfg = settings.PARAIPYTHON
    anterior = Edicao.anteriores_a(data, turno).exclude(fim_janela=None).first()
    if anterior is None:
        return fim - timedelta(hours=cfg["JANELA_HORAS"])
    return max(anterior.fim_janela, fim - timedelta(hours=cfg["JANELA_MAXIMA_HORAS"]))


# ---------------------------------------------------------------------------
# Não repetir notícias de uma edição para outra
# ---------------------------------------------------------------------------
def ja_publicadas(data, turno):
    """IDs de notícias que saíram em edições anteriores e títulos das pautas recentes.

    Os títulos pegam o caso de o portal republicar a mesma história com link novo.
    """
    comparadas = settings.PARAIPYTHON["EDICOES_COMPARADAS"]
    recentes = list(Edicao.anteriores_a(data, turno)[: max(comparadas, 6)])
    rels = EdicaoNoticia.objects.filter(edicao__in=recentes).select_related("noticia")

    ids = {rel.noticia_id for rel in rels}
    titulos = []
    comparar_com = {e.pk for e in recentes[:comparadas]}
    links_extras = []
    for rel in rels:
        if rel.edicao_id in comparar_com:
            titulos.append(rel.noticia.titulo)
            links_extras.extend(item["link"] for item in rel.outros_links)
    titulos.extend(Noticia.objects.filter(link__in=links_extras).values_list("titulo", flat=True))
    return ids, titulos


def eh_repeteco(pauta, titulos_anteriores, limiar):
    return any(
        similaridade(noticia.titulo, anterior) >= limiar
        for noticia in pauta.noticias
        for anterior in titulos_anteriores
    )


# ---------------------------------------------------------------------------
# Seleção e montagem
# ---------------------------------------------------------------------------
def distribuir_por_tema(pautas, limite, max_por_tema):
    """Manchete = pauta mais relevante. O resto entra por relevância, respeitando o teto
    por tema, e depois é agrupado na ordem das seções do jornal."""
    if not pautas:
        return []
    manchete = next((p for p in pautas if not eh_rotineira(p)), pautas[0])
    escolhidas, contagem = [], {}
    for pauta in pautas:
        if pauta is manchete:
            continue
        if len(escolhidas) + 1 >= limite:
            break
        tema = tema_da_pauta(pauta)
        if contagem.get(tema, 0) < max_por_tema:
            contagem[tema] = contagem.get(tema, 0) + 1
            escolhidas.append(pauta)
    relevancia = {id(p): i for i, p in enumerate(escolhidas)}
    escolhidas.sort(key=lambda p: (ORDEM_TEMAS.index(tema_da_pauta(p)), relevancia[id(p)]))
    return [manchete] + escolhidas


def selecionar_pautas(data, turno, limite=None, agora=None):
    cfg = settings.PARAIPYTHON
    limite = limite or cfg["NOTICIAS_POR_EDICAO"]
    fim = fim_da_janela(data, turno, agora)
    inicio = inicio_da_janela(data, turno, fim)
    ids_publicados, titulos_anteriores = ja_publicadas(data, turno)

    noticias = (
        Noticia.objects.filter(publicado_em__gt=inicio, publicado_em__lte=fim, fonte__ativa=True)
        .exclude(pk__in=ids_publicados)
        .select_related("fonte")
        .order_by("-publicado_em")
    )
    pautas = [
        p for p in agrupar_pautas(list(noticias))
        if not eh_repeteco(p, titulos_anteriores, cfg["LIMIAR_DUPLICADA"])
    ]
    selecionadas = distribuir_por_tema(ordenar_pautas(pautas), limite, cfg["MAX_POR_TEMA"])
    return selecionadas, fim


@transaction.atomic
def montar_edicao(data=None, turno=None, limite=None, agora=None):
    """Cria (ou refaz) a edição de (data, turno) com as notícias selecionadas.

    Retorna a edição, ou ``None`` se não houver nenhuma notícia nova na janela.
    """
    data = data or timezone.localdate()
    turno = turno or turno_atual(agora)
    pautas, fim = selecionar_pautas(data, turno, limite=limite, agora=agora)
    if not pautas:
        return None

    edicao = Edicao.objects.filter(data_edicao=data, turno=turno).first()
    if edicao is None:
        edicao = Edicao(data_edicao=data, turno=turno, numero_edicao=Edicao.proximo_numero())
    edicao.fim_janela = fim
    edicao.save()
    EdicaoNoticia.objects.filter(edicao=edicao).delete()

    EdicaoNoticia.objects.bulk_create(
        [
            EdicaoNoticia(
                edicao=edicao,
                noticia=pauta.principal,
                posicao=posicao,
                tema=tema_da_pauta(pauta),
                outras_fontes=", ".join(f for f in pauta.fontes if f != pauta.principal.fonte.nome),
                outros_links=links_de_outros_portais(pauta),
            )
            for posicao, pauta in enumerate(pautas)
        ]
    )
    return edicao
