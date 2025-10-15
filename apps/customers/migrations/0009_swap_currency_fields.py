from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('customers', '0008_copy_currency_data'),
    ]

    operations = [
        # Remove old currency CharField
        migrations.RemoveField(
            model_name='account',
            name='currency',
        ),
        # Rename currency_new to currency
        migrations.RenameField(
            model_name='account',
            old_name='currency_new',
            new_name='currency',
        ),
        # Make it non-nullable
        migrations.AlterField(
            model_name='account',
            name='currency',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='accounts',
                to='customers.currency'
            ),
        ),
    ]