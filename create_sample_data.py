from django.contrib.auth.models import User
from apps.customers.models import Customer
from apps.purchase_orders.models import PurchaseOrder
from apps.billing.models import BillingRun
from apps.rate_cards.models import RateCard
from datetime import date, timedelta
import random

# Get or create admin user
try:
    admin_user = User.objects.get(username='admin')
except User.DoesNotExist:
    admin_user = User.objects.create_user('admin', 'admin@example.com', 'admin123')
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()

# Create sample customers
customers_data = [
    {'name': 'HCL Technologies', 'code': 'HCL', 'email': 'billing@hcl.com'},
    {'name': 'Cognizant', 'code': 'CTS', 'email': 'accounts@cognizant.com'},
    {'name': 'TCS', 'code': 'TCS', 'email': 'finance@tcs.com'},
    {'name': 'Atos', 'code': 'ATO', 'email': 'billing@atos.net'},
    {'name': 'Capgemini', 'code': 'CAP', 'email': 'accounts@capgemini.com'},
]

customers = []
for customer_data in customers_data:
    customer, created = Customer.objects.get_or_create(
        code=customer_data['code'],
        defaults={
            'name': customer_data['name'],
            'email': customer_data['email'],
            'phone': f'+1-555-{random.randint(1000, 9999)}',
            'address': f'{random.randint(100, 999)} Business St, Tech City',
            'created_by': admin_user
        }
    )
    customers.append(customer)
    print(f'{"Created" if created else "Found"} customer: {customer.name}')

# Create sample purchase orders
today = date.today()
for i, customer in enumerate(customers):
    for j in range(random.randint(1, 3)):  # 1-3 POs per customer
        po_number = f'PO-{customer.code}-2025-{str(j+1).zfill(3)}'
        total_amount = random.randint(50000, 500000)
        
        po, created = PurchaseOrder.objects.get_or_create(
            po_number=po_number,
            defaults={
                'customer': customer,
                'total_amount': total_amount,
                'remaining_balance': total_amount * random.uniform(0.2, 1.0),  # Random usage
                'valid_from': today - timedelta(days=random.randint(0, 30)),
                'valid_until': today + timedelta(days=random.randint(30, 365)),
                'created_by': admin_user
            }
        )
        print(f'{"Created" if created else "Found"} PO: {po.po_number}')

print('Sample data created successfully!')