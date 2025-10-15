from django.core.management.base import BaseCommand
from apps.purchase_orders.models import PurchaseOrder
from datetime import date

class Command(BaseCommand):
    help = 'Update Purchase Order statuses based on dates and balances'

    def handle(self, *args, **options):
        today = date.today()
        updated_count = 0
        
        # Get all active POs
        pos = PurchaseOrder.objects.all()
        
        for po in pos:
            old_status = po.status
            
            # Check expiry
            if po.valid_until < today:
                po.status = 'expired'
            elif (po.valid_until - today).days <= 30:
                po.status = 'expiring_soon'
            elif po.remaining_balance <= 0:
                po.status = 'expired'
            elif po.status == 'draft':
                po.status = 'draft'
            else:
                po.status = 'active'
            
            if old_status != po.status:
                po.save()
                updated_count += 1
                self.stdout.write(
                    f'Updated PO {po.po_number}: {old_status} → {po.status}'
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} Purchase Orders')
        )