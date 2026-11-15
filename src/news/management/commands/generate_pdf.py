"""Regera o PDF de uma edição já montada, sem coletar nada.

Útil para ajustar o layout do template e ver o resultado:
    python manage.py generate_pdf                 # edição mais recente
    python manage.py generate_pdf --data 2026-11-15
    python manage.py generate_pdf --html saida.html   # também grava o HTML para depurar no navegador
"""
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from news.models import Edicao
from news.services.pdf_generator import gerar_pdf_da_edicao, renderizar_html


class Command(BaseCommand):
    help = "Regera o PDF de uma edição existente."

    def add_arguments(self, parser):
        parser.add_argument("--data", help="Data da edição (AAAA-MM-DD). Padrão: a mais recente.")
        parser.add_argument("--html", help="Caminho para salvar também o HTML renderizado.")

    def handle(self, *args, **opts):
        if opts["data"]:
            try:
                edicao = Edicao.objects.get(data_edicao=date.fromisoformat(opts["data"]))
            except (ValueError, Edicao.DoesNotExist):
                raise CommandError(f"Nenhuma edição em {opts['data']}.")
        else:
            edicao = Edicao.objects.first()
            if edicao is None:
                raise CommandError("Ainda não existe nenhuma edição. Rode fetch_daily_news antes.")

        if opts["html"]:
            Path(opts["html"]).write_text(renderizar_html(edicao), encoding="utf-8")
            self.stdout.write(f"HTML salvo em {opts['html']}")

        gerar_pdf_da_edicao(edicao)
        self.stdout.write(self.style.SUCCESS(f"PDF de {edicao} salvo em media/{edicao.arquivo_pdf.name}"))
