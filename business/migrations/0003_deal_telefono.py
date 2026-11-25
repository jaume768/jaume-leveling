from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0002_deal_rechazado_por_precio"),
    ]

    operations = [
        migrations.AddField(
            model_name="deal",
            name="telefono",
            field=models.CharField(
                blank=True,
                help_text="Con o sin prefijo. Sin él, el botón de WhatsApp abre el mensaje para elegir el chat.",
                max_length=30,
                verbose_name="teléfono / WhatsApp",
            ),
        ),
    ]
