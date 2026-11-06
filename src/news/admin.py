from django.contrib import admin
from .models import FonteNoticia, Noticia, Edicao

@admin.register(FonteNoticia)
class FonteNoticiaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'url_rss', 'ativa', 'criado_em')
    list_filter = ('ativa',)
    search_fields = ('nome', 'url_rss')

@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'fonte', 'publicado_em', 'coletado_em')
    list_filter = ('fonte', 'publicado_em')
    search_fields = ('titulo', 'resumo', 'conteudo_limpo')
    ordering = ('-publicado_em',)

@admin.register(Edicao)
class EdicaoAdmin(admin.ModelAdmin):
    list_display = ('numero_edicao', 'data_edicao', 'gerado_em', 'arquivo_pdf')
    ordering = ('-data_edicao',)
    filter_horizontal = ('noticias',)