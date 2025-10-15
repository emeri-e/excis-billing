# Generated manually
from django.db import migrations, models

def migrate_currency_to_fk(apps, schema_editor):
    """Convert currency CharField to ForeignKey"""
    Account = apps.get_model('customers', 'Account')
    Currency = apps.get_model('customers', 'Currency')
    
    # For each account, find the matching currency and update
    for account in Account.objects.all():
        old_currency_code = account.currency  # This is still a CharField at this point
        
        # Find or create the currency object
        try:
            currency_obj = Currency.objects.get(code=old_currency_code)
        except Currency.DoesNotExist:
            # Create it if it doesn't exist
            currency_obj = Currency.objects.create(
                code=old_currency_code,
                name=old_currency_code,
                symbol='',
                is_active=True
            )
            print(f"Created currency: {old_currency_code}")
        
        # Store the currency_id for later (we'll use raw SQL)
        # We can't update the FK yet because the field hasn't changed type
        account._temp_currency_id = currency_obj.id
        print(f"Account {account.id}: {old_currency_code} -> Currency ID {currency_obj.id}")

def reverse_func(apps, schema_editor):
    pass  # Cannot reverse this easily

class Migration(migrations.Migration):
    dependencies = [
        ('customers', '0006_create_default_projects'),
    ]

    operations = [
        # First, add a temporary field to store the currency FK
        migrations.AddField(
            model_name='account',
            name='currency_new',
            field=models.ForeignKey(
                on_delete=models.deletion.PROTECT,
                related_name='accounts_new',
                to='customers.currency',
                null=True,
                blank=True
            ),
        ),
    ]