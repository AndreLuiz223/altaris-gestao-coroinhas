from django.contrib import admin

from .models import Atribuicao, Celebracao, Comunidade, PagamentoTunica, Servidor, Tunica


@admin.register(Comunidade)
class ComunidadeAdmin(admin.ModelAdmin):
    search_fields = ["nome"]


@admin.register(Servidor)
class ServidorAdmin(admin.ModelAdmin):
    list_display = ["nome", "comunidade", "tipo", "nivel", "status"]
    list_filter = ["comunidade", "tipo", "nivel", "status"]
    search_fields = ["nome"]


class AtribuicaoInline(admin.TabularInline):
    model = Atribuicao
    extra = 0


@admin.register(Celebracao)
class CelebracaoAdmin(admin.ModelAdmin):
    list_display = ["titulo", "comunidade", "data_hora_inicio", "publicada"]
    list_filter = ["comunidade", "publicada", "tipo"]
    readonly_fields = ["token_publico"]
    inlines = [AtribuicaoInline]


class PagamentoInline(admin.TabularInline):
    model = PagamentoTunica
    extra = 0


@admin.register(Tunica)
class TunicaAdmin(admin.ModelAdmin):
    list_display = ["servidor", "modelo", "valor_total", "saldo"]
    inlines = [PagamentoInline]
