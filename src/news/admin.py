from django.contrib import admin
from django.utils.html import format_html

from .models import Edicao, EdicaoNoticia, FonteNoticia, Noticia

admin.site.site_header = "Expresso PB — Redação"
admin.site.site_title = "Expresso PB"
admin.site.index_title = "Bastidores do cafezinho"


@admin.register(FonteNoticia)
class FonteNoticiaAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "url", "ativa", "criado_em")
    list_filter = ("ativa", "tipo")
    list_editable = ("ativa",)
    search_fields = ("nome", "url")


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "tema", "fonte", "categoria", "publicado_em")
    list_filter = ("tema", "fonte", "publicado_em")
    list_editable = ("tema",)  # corrija o tema na própria lista
    search_fields = ("titulo", "resumo")
    date_hierarchy = "publicado_em"
    ordering = ("-publicado_em",)


class EdicaoNoticiaInline(admin.TabularInline):
    model = EdicaoNoticia
    extra = 0
    autocomplete_fields = ("noticia",)
    fields = ("posicao", "tema", "noticia", "outras_fontes")


@admin.register(Edicao)
class EdicaoAdmin(admin.ModelAdmin):
    list_display = ("numero_edicao", "data_edicao", "turno", "total_noticias", "link_pdf", "fim_janela")
    list_filter = ("turno",)
    ordering = ("-data_edicao", "-turno")
    readonly_fields = ("data_criacao", "atualizado_em", "fim_janela")
    inlines = [EdicaoNoticiaInline]

    @admin.display(description="Notícias")
    def total_noticias(self, obj):
        return obj.noticias.count()

    @admin.display(description="PDF")
    def link_pdf(self, obj):
        if not obj.arquivo_pdf:
            return "—"
        return format_html('<a href="{}" target="_blank">abrir</a>', obj.get_pdf_url())
