# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('casas', '0003_auto_20200207_0919'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casalegislativa',
            name='gerente_contas',
            field=models.ForeignKey(related_name='casas_que_gerencia_old', verbose_name=b'Gerente de contas', blank=True, to='servidores.Servidor', null=True),
            preserve_default=True,
        ),
    ]
