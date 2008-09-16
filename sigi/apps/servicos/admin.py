# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.contenttypes import generic
from sigi.apps.contatos.models import Contato
from sigi.apps.servicos.models import Servico

class ContatosInline(generic.GenericTabularInline):
    model = Contato
    extra = 1
    verbose_name = 'colaborador Interlegis'
    verbose_name_plural = 'colaboradores Interlegis'

class ServicoAdmin(admin.ModelAdmin):
    date_hierarchy = 'data_inicio'
    inlines = (ContatosInline,)
    list_display = ('id', 'titulo', 'tipo', 'situacao', 'avaliacao')
    list_filter  = ('tipo','situacao', 'avaliacao',)
    search_fields = ('titulo', 'tipo', 'descricao',)

admin.site.register(Servico, ServicoAdmin)
