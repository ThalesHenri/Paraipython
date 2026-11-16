"""Coleta de notícias via RSS.

Separado em duas partes para facilitar os testes:
- ``baixar_feed``: só a parte de rede (com timeout e retentativas);
- ``extrair_itens``: transforma o XML em dicionários limpos, sem tocar no banco.
"""
import html
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone

import feedparser
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from news.models import FonteNoticia, Noticia
from news.services.temas import classificar

logger = logging.getLogger(__name__)

TENTATIVAS = 3
ESPERA_ENTRE_TENTATIVAS = 5  # segundos
MAX_ITENS_POR_FEED = 40

# Frases de "chamada" que os portais enfiam no meio do texto e não são notícia.
RUIDO = re.compile(
    r"(✅\s*)?Clique aqui para seguir o canal do g1[^.]*?WhatsApp|"
    r"Vídeos mais assistidos do g1[^.]*|Agora no g1|Leia também:?",
    re.IGNORECASE,
)


def _config(chave):
    return settings.PARAIPYTHON[chave]


@dataclass
class ResultadoColeta:
    fonte: FonteNoticia
    novas: int = 0
    repetidas: int = 0
    erros: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.erros


# ---------------------------------------------------------------------------
# Rede
# ---------------------------------------------------------------------------
def baixar_feed(url, tentativas=TENTATIVAS, espera=ESPERA_ENTRE_TENTATIVAS):
    """Baixa o feed com timeout (o feedparser sozinho não tem) e retentativas."""
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(
                url,
                timeout=_config("TIMEOUT_HTTP"),
                headers={"User-Agent": _config("USER_AGENT")},
            )
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            ultimo_erro = exc
            logger.warning("Tentativa %s/%s falhou para %s: %s", tentativa, tentativas, url, exc)
            if tentativa < tentativas:
                time.sleep(espera)
    raise ultimo_erro


# ---------------------------------------------------------------------------
# Limpeza de texto
# ---------------------------------------------------------------------------
def limpar_texto(texto):
    """Remove HTML, entidades, ruídos de portal e espaços repetidos."""
    if not texto:
        return ""
    texto = BeautifulSoup(texto, "html.parser").get_text(" ")
    texto = html.unescape(texto)
    texto = RUIDO.sub(" ", texto)
    return re.sub(r"\s+", " ", texto).strip()


# ---------------------------------------------------------------------------
# Resumo por frases (sem reticências)
# ---------------------------------------------------------------------------
# Palavras que terminam com ponto mas não encerram a frase ("Sr. Fulano", "Av. Epitácio").
ABREVIACOES = {
    "sr", "sra", "srta", "dr", "dra", "prof", "profa", "av", "jr", "dep", "gov", "pres",
    "min", "sen", "ver", "cel", "sgt", "cap", "ten", "gen", "maj", "exmo", "exma", "vol",
    "pag", "art", "inc", "ltda", "cia", "nº", "no", "n", "tel", "aprox", "obs", "ex",
}
FIM_DE_FRASE = re.compile(r"[.!?…]+[\"”’)]*\s+")
PONTUACAO_FINAL = re.compile(r"[.!?…][\"”’)]*$")


def dividir_frases(texto):
    """Divide em frases sem confundir abreviações, iniciais ("J. Silva") e números."""
    frases, inicio = [], 0
    for m in FIM_DE_FRASE.finditer(texto):
        fim = m.end()
        proximo = texto[fim:fim + 1]
        if not proximo or not (proximo.isupper() or proximo.isdigit() or proximo in "\"“'‘"):
            continue
        palavra = re.search(r"(\S+)$", texto[:m.start()])
        anterior = palavra.group(1).lower().strip("(\"“") if palavra else ""
        if anterior in ABREVIACOES or (len(anterior) == 1 and anterior.isalpha()):
            continue
        frases.append(texto[inicio:fim].strip())
        inicio = fim
    resto = texto[inicio:].strip()
    if resto:
        frases.append(resto)
    return frases


def _fechar_frase(texto):
    """Garante pontuação final ("... de brigas" → "... de brigas.")."""
    texto = texto.strip().rstrip(",;:-–— ")
    if not PONTUACAO_FINAL.search(texto):
        texto += "."
    return texto


def resumir(texto, limite=None, teto=None):
    """Junta frases inteiras até o limite. Se a 1ª frase sozinha passar do limite,
    aceita até o teto para não cortá-la. Devolve ``None`` se nem isso couber."""
    limite = limite or _config("TAMANHO_RESUMO")
    teto = teto or _config("TETO_RESUMO")
    texto = (texto or "").strip()
    if not texto:
        return None
    if len(texto) <= limite:
        return _fechar_frase(texto)

    frases = dividir_frases(texto)
    resumo = ""
    for frase in frases:
        candidato = f"{resumo} {frase}".strip()
        if len(candidato) > limite:
            break
        resumo = candidato
    if resumo:
        return _fechar_frase(resumo)
    if len(frases[0]) <= teto:
        return _fechar_frase(frases[0])
    return None


def cortar_com_reticencias(texto, limite=None):
    """Último recurso, quando nenhuma fonte tem frase que caiba no teto."""
    limite = limite or _config("TAMANHO_RESUMO")
    corte = texto[:limite].rsplit(" ", 1)[0].rstrip(",;:-–— ")
    return corte + "…"


def melhor_resumo(candidatos):
    """Tenta cada texto candidato, na ordem de preferência, até um fechar a frase."""
    candidatos = [c for c in candidatos if c]
    for texto in candidatos:
        resumo = resumir(texto)
        if resumo:
            return resumo
    return cortar_com_reticencias(candidatos[0]) if candidatos else ""


def _paragrafos_do_conteudo(html_conteudo):
    """Pega só os <p> do content:encoded, ignorando figuras, legendas e listas."""
    soup = BeautifulSoup(html_conteudo, "html.parser")
    for lixo in soup.find_all(["figure", "figcaption", "picture", "script", "style"]):
        lixo.decompose()
    paragrafos = [limpar_texto(p.get_text(" ")) for p in soup.find_all("p")]
    return " ".join(p for p in paragrafos if p)


def _sem_titulo_no_inicio(texto, titulo):
    """O description do G1 repete o título no começo; tiramos."""
    if titulo and texto.lower().startswith(titulo.lower()):
        return texto[len(titulo):].strip()
    return texto


def candidatos_do_conteudo(conteudo_html, titulo):
    """Textos que podem virar resumo a partir do HTML guardado em ``conteudo_bruto``."""
    return [
        _paragrafos_do_conteudo(conteudo_html),
        _sem_titulo_no_inicio(limpar_texto(conteudo_html), titulo),
    ]


def _resumo_do_item(item, titulo):
    candidatos = [
        # 1) G1: <atom:subtitle> é a linha fina, o melhor resumo possível.
        limpar_texto(item.get("subtitle", "")),
    ]
    # 2) Jornal da Paraíba: o <description> começa com o crédito da foto,
    #    então preferimos os parágrafos do content:encoded.
    for conteudo in item.get("content", []):
        candidatos.append(_paragrafos_do_conteudo(conteudo.get("value", "")))
    # 3) Último recurso: o description, sem o título repetido no início (padrão do G1).
    candidatos.append(_sem_titulo_no_inicio(limpar_texto(item.get("summary", "")), titulo))
    return melhor_resumo(candidatos)


def _data_publicacao(item, agora):
    struct = item.get("published_parsed") or item.get("updated_parsed")
    if not struct:
        return agora
    data = datetime(*struct[:6], tzinfo=dt_timezone.utc)
    texto_data = (item.get("published") or item.get("updated") or "").strip()
    # Pela RFC 2822, "-0000" = "horário local, fuso desconhecido". O G1 usa isso
    # com o horário de Brasília/Nordeste, então tratamos como horário local.
    if texto_data.endswith("-0000"):
        data = timezone.make_aware(data.replace(tzinfo=None), timezone.get_current_timezone())
    # Data no futuro não faz sentido para notícia: usamos o momento da coleta.
    if data > agora + timedelta(minutes=10):
        return agora
    return data


def extrair_itens(conteudo_xml, agora=None):
    """Converte o XML do feed numa lista de dicionários prontos para virar Noticia."""
    agora = agora or timezone.now()
    feed = feedparser.parse(conteudo_xml)
    if feed.bozo and not feed.entries:
        raise ValueError(f"Feed inválido: {feed.bozo_exception}")

    itens = []
    for item in feed.entries[:MAX_ITENS_POR_FEED]:
        titulo = limpar_texto(item.get("title", ""))
        link = (item.get("link") or "").strip()
        if not titulo or not link:
            continue
        tags = item.get("tags") or []
        categoria = limpar_texto(tags[0].get("term", "")) if tags else ""
        if categoria.upper() == "G1":  # o G1 põe o nome do portal como categoria
            categoria = ""
        conteudo = item.get("content", [{}])[0].get("value", "") or item.get("summary", "")
        resumo = _resumo_do_item(item, titulo)
        itens.append(
            {
                "titulo": titulo[:300],
                "link": link[:500],
                "resumo": resumo,
                "categoria": categoria[:100],
                "tema": classificar(titulo, resumo, categoria, link),
                "conteudo_bruto": conteudo,
                "publicado_em": _data_publicacao(item, agora),
            }
        )
    return itens


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------
def salvar_itens(fonte, itens, resultado):
    for dados in itens:
        try:
            with transaction.atomic():
                _, criada = Noticia.objects.get_or_create(
                    link=dados["link"], defaults={**dados, "fonte": fonte}
                )
        except IntegrityError as exc:
            resultado.erros.append(f"{dados['titulo']}: {exc}")
            continue
        if criada:
            resultado.novas += 1
        else:
            resultado.repetidas += 1


def coletar_fonte(fonte, conteudo_xml=None):
    """Coleta uma fonte. ``conteudo_xml`` permite injetar o feed (testes / arquivo local)."""
    resultado = ResultadoColeta(fonte=fonte)
    if fonte.tipo != FonteNoticia.Tipo.RSS:
        resultado.erros.append("Tipo 'scraping' ainda não implementado — fonte ignorada.")
        return resultado
    try:
        if conteudo_xml is None:
            conteudo_xml = baixar_feed(fonte.url)
        itens = extrair_itens(conteudo_xml)
    except Exception as exc:  # uma fonte quebrada não derruba as outras
        logger.exception("Falha ao coletar %s", fonte.nome)
        resultado.erros.append(str(exc))
        return resultado
    salvar_itens(fonte, itens, resultado)
    return resultado


def coletar_todas(pausa_entre_fontes=2):
    resultados = []
    fontes = list(FonteNoticia.objects.filter(ativa=True, tipo=FonteNoticia.Tipo.RSS))
    for i, fonte in enumerate(fontes):
        if i:
            time.sleep(pausa_entre_fontes)
        resultados.append(coletar_fonte(fonte))
    return resultados
