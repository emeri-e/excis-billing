import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.customers.models import Customer, Account 

User = get_user_model()
logger = logging.getLogger('customers')

class Command(BaseCommand):
    help = 'Test customer and account data for debugging'

    def handle(self, *args, **options):
        logger.info("🚀 Starting customer data test command")
        self.stdout.write("🚀 Testing customer data...")
        
        try:
            # Test 1: Database connection and model access
            logger.info("Test 1: Checking database connection and models")
            
            total_customers = Customer.objects.count()
            active_customers = Customer.objects.filter(is_active=True).count()
            
            logger.info(f"Total customers: {total_customers}")
            logger.info(f"Active customers: {active_customers}")
            
            total_accounts = Account.objects.count()
            active_accounts = Account.objects.filter(is_active=True).count()
            
            logger.info(f"Total accounts: {total_accounts}")
            logger.info(f"Active accounts: {active_accounts}")
            
            # Test 2: Sample data inspection
            logger.info("Test 2: Sample data inspection")
            
            if total_customers > 0:
                customer = Customer.objects.first()
                logger.info(f"Sample customer: {customer}")
                logger.info(f"Customer fields: {[f.name for f in customer._meta.fields]}")
                
                # Check if customer has accounts
                customer_accounts = customer.accounts.all().count() if hasattr(customer, 'accounts') else 0
                logger.info(f"This customer has {customer_accounts} accounts")
            
            if total_accounts > 0:
                account = Account.objects.first()
                logger.info(f"Sample account: {account}")
                logger.info(f"Account fields: {[f.name for f in account._meta.fields]}")
                logger.info(f"Account customer: {account.customer}")
            
            # Test 3: Simulate the view logic
            logger.info("Test 3: Simulating view logic")
            
            from apps.customers.views import customer_accounts_list
            
            # Create a fake request object
            class FakeRequest:
                def __init__(self):
                    self.user = User.objects.first() or User.objects.create_user('test', 'test@example.com', 'password')
            
            fake_request = FakeRequest()
            
            # This will trigger all the logging in your view
            logger.info("Calling customer_accounts_list view...")
            response = customer_accounts_list(fake_request)
            logger.info(f"View returned response with status: {response.status_code}")
            
            self.stdout.write(
                self.style.SUCCESS("✅ Test completed! Check the log files for detailed information.")
            )
            
        except Exception as e:
            logger.error(f"❌ Error during testing: {e}", exc_info=True)
            self.stdout.write(
                self.style.ERROR(f"❌ Error: {e}")
            )