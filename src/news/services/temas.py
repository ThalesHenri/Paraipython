"""Classifica cada notícia num tema (seção do jornal).

Como funciona:
- cada tema tem uma lista de palavras-chave (sem acento, minúsculas);
- palavra no título vale 2 pontos, no resumo vale 1;
- a categoria do portal (o Jornal da Paraíba manda "Esportes", "Política"...) dá um bônus;
- vence o tema com mais pontos; sem nenhum ponto, a notícia vai para Cidade.

Para ajustar, edite as listas abaixo e rode ``python manage.py reprocessar_noticias``.
"""
import re
import unicodedata

from news.temas import Tema

# Palavras inteiras, sem acento. Com "*" no fim vira radical: "assassin*" pega
# assassinato, assassinado... Hífen casa com espaço ou hífen ("sao-joao").
PALAVRAS = {
    Tema.POLICIA: """
        policia policial policiais preso presa presos prisao prende* homicidio* assassin*
        morto morta mortos mata matou matar faca facada tiro tiros baleado baleada
        crime crimes criminos* suspeito suspeita suspeitos delegacia delegado droga drogas
        trafico assalto* roubo roubada roubado furto acidente acidentes colisao capot*
        atropel* flagrante emboscada corpo foragido mandado mandados operacao investig*
        vitima violencia agressao agredi* golpe golpes presidio atira* atirou atingid*
        disparo* esfaque* sequestr*
    """,
    Tema.POLITICA: """
        governo governador governadora prefeito prefeita vereador vereadora vereadores
        deputado deputada deputados assembleia alpb senador senadora eleicao eleicoes
        eleitoral partido mandato tse tre candidato candidata ministro ministra presidente
        lula congresso camara-municipal secretario secretaria projeto-de-lei sancion* vetad*
    """,
    Tema.ECONOMIA: """
        emprego empregos desemprego salario salarios inflacao preco precos comercio
        concurso concursos inss imposto impostos ipva iptu empresa empresas combustivel
        gasolina sine vagas economia economic* consumidor consumidores procon pib ibge
        black-friday decimo-terceiro aposentadoria fgts
    """,
    Tema.EDUCACAO: """
        enem escola escolas aluno alunos aluna estudante estudantes professor professora
        professores universidade universidades ufpb uepb ifpb vestibular sisu matricula*
        aula aulas educacao ensino faculdade redacao
    """,
    Tema.SAUDE: """
        saude hospital hospitais vacina vacinas vacinacao sus dengue chikungunya covid upa
        doenca doencas cancer hemocentro sangue cirurgia paciente pacientes surto virus
        epidemia medicamento* remedio* hemodialise
    """,
    Tema.CLIMA: """
        chuva chuvas chover inmet temporal temperatura temperaturas calor frio praia praias
        mar mares mare ambiente ambiental desmatamento aesa seca estiagem ventos vendaval
        enchente* alagamento* previsao-do-tempo clima climatic* reciclagem lixo poluicao
        animal animais resgatado resgatada
    """,
    Tema.ESPORTES: """
        botafogo-pb botafogo treze campinense paraibano futebol gol gols campeonato almeidao
        amigao serie-c serie-d atleta atletas corrida maratona torcida tecnico partida
        vence venceu empate rodada copa
    """,
    Tema.CULTURA: """
        show shows festival festa festas sao-joao musica musico cantor cantora cinema
        cinemas filme teatro exposicao turismo turistas carnaval artista artistas livro
        livros literaria literario cultura cultural espetaculo apresentacao forro orquestra
        receita receitas
    """,
}

# Categoria do portal → tema (bônus, não decisão: "Cotidiano" do JP inclui crimes).
CATEGORIAS = {
    "esportes": Tema.ESPORTES,
    "esporte": Tema.ESPORTES,
    "politica": Tema.POLITICA,
    "economia": Tema.ECONOMIA,
    "educacao": Tema.EDUCACAO,
    "saude": Tema.SAUDE,
    "meio ambiente": Tema.CLIMA,
    "clima": Tema.CLIMA,
    "cultura": Tema.CULTURA,
    "entretenimento": Tema.CULTURA,
    "policia": Tema.POLICIA,
    "seguranca": Tema.POLICIA,
}
BONUS_CATEGORIA = 3


def normalizar(texto):
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c)
    )
    return sem_acento.lower()


def _compilar():
    regras = {}
    for tema, palavras in PALAVRAS.items():
        termos = []
        for palavra in palavras.split():
            radical = palavra.endswith("*")
            termo = re.escape(palavra.rstrip("*")).replace(r"\-", r"[\s-]").replace("-", r"[\s-]")
            termos.append(termo + (r"\w*" if radical else r"\b"))
        regras[tema] = re.compile(r"\b(?:" + "|".join(termos) + ")", re.IGNORECASE)
    return regras


REGRAS = _compilar()


def pontuar(titulo, resumo="", categoria="", link=""):
    titulo_n, resumo_n = normalizar(titulo), normalizar(resumo)
    pontos = {}
    for tema, regra in REGRAS.items():
        total = 2 * len(regra.findall(titulo_n)) + len(regra.findall(resumo_n))
        if total:
            pontos[tema] = total
    tema_categoria = CATEGORIAS.get(normalizar(categoria).strip())
    if tema_categoria:
        pontos[tema_categoria] = pontos.get(tema_categoria, 0) + BONUS_CATEGORIA
    if "ge.globo.com" in (link or ""):
        pontos[Tema.ESPORTES] = pontos.get(Tema.ESPORTES, 0) + BONUS_CATEGORIA
    return pontos


def classificar(titulo, resumo="", categoria="", link=""):
    pontos = pontuar(titulo, resumo, categoria, link)
    if not pontos:
        return Tema.CIDADE
    # Empate: vale a ordem das seções do jornal (Polícia antes de Política etc.).
    ordem = list(Tema)
    return max(pontos, key=lambda tema: (pontos[tema], -ordem.index(tema)))
