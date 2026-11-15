"""Cadastra os portais de João Pessoa já mapeados, para o robô funcionar logo após o migrate."""
from django.db import migrations

FONTES = [
    {
        "nome": "Jornal da Paraíba",
        "url": "https://jornaldaparaiba.com.br/feed",
        "site_url": "https://jornaldaparaiba.com.br",
        "tipo": "rss",
        "ativa": True,
    },
    {
        "nome": "g1 PB",
        "url": "https://g1.globo.com/dynamo/pb/paraiba/rss2.xml",
        "site_url": "https://g1.globo.com/pb/paraiba/",
        "tipo": "rss",
        "ativa": True,
    },
    {
        # Sem RSS: fica cadastrado, mas inativo até existir o coletor por scraping.
        "nome": "PB Agora",
        "url": "https://www.pbagora.com.br/",
        "site_url": "https://www.pbagora.com.br/",
        "tipo": "scraping",
        "ativa": False,
    },
]


def criar_fontes(apps, schema_editor):
    FonteNoticia = apps.get_model("news", "FonteNoticia")
    for dados in FONTES:
        FonteNoticia.objects.update_or_create(nome=dados["nome"], defaults=dados)


def remover_fontes(apps, schema_editor):
    FonteNoticia = apps.get_model("news", "FonteNoticia")
    FonteNoticia.objects.filter(nome__in=[f["nome"] for f in FONTES]).delete()


class Migration(migrations.Migration):
    dependencies = [("news", "0001_initial")]
    operations = [migrations.RunPython(criar_fontes, remover_fontes)]
