import feedparser
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from weasyprint import HTML
from news.models import FonteNoticia, Noticia, Edicao