# Generated by Django 4.2 on 2025-01-30 21:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0003_add_user_to_flight'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='distance',
            field=models.IntegerField(default=0),
        ),
    ]
