# Generated by Django 4.1.13 on 2025-06-26 05:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0002_alter_user_password'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='court',
            name='test',
        ),
        migrations.AlterField(
            model_name='contactus',
            name='phone',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='court',
            name='cc_fees',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='court',
            name='tax',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='courtbooking',
            name='duration_time',
            field=models.CharField(blank=True, max_length=225, null=True),
        ),
    ]
