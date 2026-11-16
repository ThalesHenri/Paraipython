"""Preenche os campos novos nos dados que já existiam:
- edições antigas viram "Edição da Manhã" com o fim da janela = momento em que foram criadas;
- notícias antigas ganham tema pelo classificador;
- cada notícia já publicada recebe a seção (tema) da própria notícia.
"""
from django.db import migrations


def preencher(apps, schema_editor):
    from news.services.temas import classificar

    Edicao = apps.get_model("news", "Edicao")
    Noticia = apps.get_model("news", "Noticia")
    EdicaoNoticia = apps.get_model("news", "EdicaoNoticia")

    for edicao in Edicao.objects.filter(fim_janela__isnull=True):
        edicao.fim_janela = edicao.data_criacao
        edicao.save(update_fields=["fim_janela"])

    for noticia in Noticia.objects.all().iterator():
        noticia.tema = classificar(noticia.titulo, noticia.resumo, noticia.categoria, noticia.link)
        noticia.save(update_fields=["tema"])

    for rel in EdicaoNoticia.objects.select_related("noticia"):
        rel.tema = rel.noticia.tema
        rel.save(update_fields=["tema"])


class Migration(migrations.Migration):
    dependencies = [("news", "0004_edicoes_por_turno_e_temas")]
    operations = [migrations.RunPython(preencher, migrations.RunPython.noop)]
