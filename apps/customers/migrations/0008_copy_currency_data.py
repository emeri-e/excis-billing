from django.db import migrations

def copy_currency_data(apps, schema_editor):
    """Copy currency codes to new FK field"""
    Account = apps.get_model('customers', 'Account')
    Currency = apps.get_model('customers', 'Currency')
    
    for account in Account.objects.all():
        old_currency_code = account.currency  # CharField
        
        try:
            currency_obj = Currency.objects.get(code=old_currency_code)
            account.currency_new = currency_obj
            account.save(update_fields=['currency_new'])
            print(f"Migrated account {account.id}: {old_currency_code}")
        except Currency.DoesNotExist:
            print(f"WARNING: Currency {old_currency_code} not found for account {account.id}")

def reverse_func(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('customers', '0007_migrate_currency_data'),
    ]

    operations = [
        migrations.RunPython(copy_currency_data, reverse_func),
    ]