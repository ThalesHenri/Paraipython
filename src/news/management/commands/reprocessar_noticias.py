"""Refaz o resumo e o tema das notícias já salvas no banco.

Use depois de ajustar as palavras-chave em ``news/services/temas.py`` ou as regras de
resumo em ``news/services/coleta.py``:
    python manage.py reprocessar_noticias
    python manage.py reprocessar_noticias --dias 3      # só as notícias dos últimos 3 dias

Edições já publicadas não mudam; o efeito aparece nas próximas (ou ao refazer uma edição).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Noticia
from news.services.coleta import candidatos_do_conteudo, melhor_resumo, resumir
from news.services.temas import classificar


class Command(BaseCommand):
    help = "Recalcula resumo (sem reticências) e tema das notícias já coletadas."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, help="Só notícias publicadas nos últimos N dias.")

    def handle(self, *args, **opts):
        noticias = Noticia.objects.all()
        if opts["dias"]:
            noticias = noticias.filter(publicado_em__gte=timezone.now() - timedelta(days=opts["dias"]))

        resumos = temas = 0
        for noticia in noticias.iterator():
            campos = []
            # O resumo antigo serve se fecha a frase; se terminava em "…", refazemos
            # a partir do conteúdo guardado do feed.
            novo_resumo = None if noticia.resumo.endswith("…") else resumir(noticia.resumo)
            if not novo_resumo:
                novo_resumo = melhor_resumo(
                    candidatos_do_conteudo(noticia.conteudo_bruto, noticia.titulo) + [noticia.resumo]
                )
            if novo_resumo and novo_resumo != noticia.resumo:
                noticia.resumo = novo_resumo
                campos.append("resumo")
                resumos += 1

            novo_tema = classificar(noticia.titulo, noticia.resumo, noticia.categoria, noticia.link)
            if novo_tema != noticia.tema:
                noticia.tema = novo_tema
                campos.append("tema")
                temas += 1

            if campos:
                noticia.save(update_fields=campos)

        self.stdout.write(self.style.SUCCESS(
            f"{noticias.count()} notícias revisadas: {resumos} resumos refeitos, {temas} temas alterados."
        ))
