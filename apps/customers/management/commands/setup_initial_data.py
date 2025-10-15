from django.core.management.base import BaseCommand
from apps.customers.models import Currency, Country


class Command(BaseCommand):
    help = 'Setup initial currencies and countries'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Setting up initial data...'))
        
        # Setup Currencies
        currencies = [
            {'code': 'USD', 'name': 'US Dollar', 'symbol': '$'},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€'},
            {'code': 'GBP', 'name': 'British Pound', 'symbol': '£'},
            {'code': 'AUD', 'name': 'Australian Dollar', 'symbol': 'A$'},
            {'code': 'INR', 'name': 'Indian Rupee', 'symbol': '₹'},
            {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥'},
            {'code': 'CAD', 'name': 'Canadian Dollar', 'symbol': 'C$'},
            {'code': 'KES', 'name': 'Kenyan Shilling', 'symbol': 'KSh'},
            {'code': 'ZAR', 'name': 'South African Rand', 'symbol': 'R'},
            {'code': 'NGN', 'name': 'Nigerian Naira', 'symbol': '₦'},
            {'code': 'GHS', 'name': 'Ghanaian Cedi', 'symbol': 'GH₵'},
            {'code': 'TZS', 'name': 'Tanzanian Shilling', 'symbol': 'TSh'},
            {'code': 'UGX', 'name': 'Ugandan Shilling', 'symbol': 'USh'},
        ]
        
        currency_count = 0
        for curr in currencies:
            currency, created = Currency.objects.get_or_create(
                code=curr['code'],
                defaults={'name': curr['name'], 'symbol': curr['symbol']}
            )
            if created:
                currency_count += 1
                self.stdout.write(f"  ✓ Created currency: {curr['code']} - {curr['name']}")
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Added {currency_count} currencies'))
        
        # Setup Countries
        countries = [
            {'code': 'USA', 'name': 'United States'},
            {'code': 'GBR', 'name': 'United Kingdom'},
            {'code': 'CAN', 'name': 'Canada'},
            {'code': 'AUS', 'name': 'Australia'},
            {'code': 'IND', 'name': 'India'},
            {'code': 'KEN', 'name': 'Kenya'},
            {'code': 'ZAF', 'name': 'South Africa'},
            {'code': 'NGA', 'name': 'Nigeria'},
            {'code': 'GHA', 'name': 'Ghana'},
            {'code': 'TZA', 'name': 'Tanzania'},
            {'code': 'UGA', 'name': 'Uganda'},
            {'code': 'DEU', 'name': 'Germany'},
            {'code': 'FRA', 'name': 'France'},
            {'code': 'ITA', 'name': 'Italy'},
            {'code': 'ESP', 'name': 'Spain'},
            {'code': 'JPN', 'name': 'Japan'},
            {'code': 'CHN', 'name': 'China'},
            {'code': 'BRA', 'name': 'Brazil'},
            {'code': 'MEX', 'name': 'Mexico'},
            {'code': 'SGP', 'name': 'Singapore'},
        ]
        
        country_count = 0
        for ctry in countries:
            country, created = Country.objects.get_or_create(
                code=ctry['code'],
                defaults={'name': ctry['name']}
            )
            if created:
                country_count += 1
                self.stdout.write(f"  ✓ Created country: {ctry['code']} - {ctry['name']}")
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Added {country_count} countries'))
        self.stdout.write(self.style.SUCCESS('\n✓ Initial data setup complete!'))