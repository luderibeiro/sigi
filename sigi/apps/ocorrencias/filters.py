# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.translation import ugettext as _

from sigi.apps.servidores.models import Servidor


class OcorrenciaListFilter(admin.SimpleListFilter):

    title = _(u'Relacionadas a Mim')
    parameter_name = 'minhas'

    def lookups(self, request, model_admin):
        return (
            ('S', _(u'Atribuídos ao meu setor')),
            ('M', _(u'Registrados por mim')),
        )

    def queryset(self, request, queryset):
        servidor = Servidor.objects.get(user=request.user)
        if self.value() == 'S':
            return queryset.filter(setor_responsavel=servidor.servico)
        if self.value() == 'M':
            return queryset.filter(servidor_registro=servidor)
