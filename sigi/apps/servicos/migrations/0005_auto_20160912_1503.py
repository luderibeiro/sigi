# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-09-12 15:03
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('servicos', '0004_auto_20160623_0829'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casamanifesta',
            name='casa_legislativa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='casas.CasaLegislativa'),
        ),
    ]
