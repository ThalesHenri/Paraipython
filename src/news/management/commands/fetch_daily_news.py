"""Robô diário do Expresso PB: coleta → monta a edição → gera o PDF.

Uso típico (cron às 06:00):
    python manage.py fetch_daily_news

Outras formas:
    python manage.py fetch_daily_news --sem-pdf             # só coleta e monta
    python manage.py fetch_daily_news --sem-coleta          # remonta com o que já está no banco
    python manage.py fetch_daily_news --feed-local "g1 PB=/caminho/feed.xml"   # testa offline
"""
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.models import FonteNoticia
from news.services.coleta import coletar_fonte, coletar_todas
from news.services.montagem import montar_edicao
from news.services.pdf_generator import gerar_pdf_da_edicao


class Command(BaseCommand):
    help = "Coleta os feeds RSS, monta a edição do dia e gera o PDF retrô."

    def add_arguments(self, parser):
        parser.add_argument("--data", help="Data da edição (AAAA-MM-DD). Padrão: hoje.")
        parser.add_argument("--sem-coleta", action="store_true", help="Não baixa os feeds.")
        parser.add_argument("--sem-pdf", action="store_true", help="Não gera o PDF.")
        parser.add_argument(
            "--feed-local", action="append", default=[], metavar="FONTE=ARQUIVO",
            help="Usa um arquivo XML local no lugar do feed da fonte (pode repetir).",
        )

    def handle(self, *args, **opts):
        data = self._data(opts["data"])

        if not opts["sem_coleta"]:
            self._coletar(opts["feed_local"])

        edicao = montar_edicao(data)
        if edicao is None:
            self.stdout.write(self.style.WARNING(
                "Nenhuma notícia na janela de tempo da edição — nada a publicar hoje."
            ))
            return
        total = edicao.noticias.count()
        self.stdout.write(self.style.SUCCESS(f"{edicao} montada com {total} notícias."))

        if not opts["sem_pdf"]:
            gerar_pdf_da_edicao(edicao)
            self.stdout.write(self.style.SUCCESS(f"PDF salvo em media/{edicao.arquivo_pdf.name}"))

    # ------------------------------------------------------------------
    def _data(self, valor):
        if not valor:
            return timezone.localdate()
        try:
            return date.fromisoformat(valor)
        except ValueError:
            raise CommandError("Use a data no formato AAAA-MM-DD.")

    def _coletar(self, feeds_locais):
        self.stdout.write("Coletando notícias...")
        if feeds_locais:
            resultados = []
            for par in feeds_locais:
                nome, _, caminho = par.partition("=")
                try:
                    fonte = FonteNoticia.objects.get(nome=nome.strip())
                except FonteNoticia.DoesNotExist:
                    raise CommandError(f"Fonte '{nome}' não cadastrada.")
                resultados.append(coletar_fonte(fonte, Path(caminho.strip()).read_bytes()))
        else:
            resultados = coletar_todas()

        if not resultados:
            self.stdout.write(self.style.WARNING("Nenhuma fonte RSS ativa cadastrada."))
        for r in resultados:
            linha = f"  {r.fonte.nome}: {r.novas} novas, {r.repetidas} já conhecidas"
            if r.ok:
                self.stdout.write(self.style.SUCCESS(linha))
            else:
                self.stdout.write(self.style.ERROR(f"{linha} — ERRO: {'; '.join(r.erros)[:300]}"))
