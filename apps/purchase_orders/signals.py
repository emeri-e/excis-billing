from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import PurchaseOrder, POBalanceNotification
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=PurchaseOrder)
def check_balance_thresholds(sender, instance, **kwargs):
    """Check if PO balance has crossed notification thresholds"""
    
    # Skip for new records (no pk yet)
    if not instance.pk:
        return
    
    try:
        # Get the previous instance to compare
        old_instance = PurchaseOrder.objects.get(pk=instance.pk)
    except PurchaseOrder.DoesNotExist:
        return
    
    # Skip if balance hasn't changed
    old_remaining = old_instance.total_amount - old_instance.spent_amount
    new_remaining = instance.total_amount - instance.spent_amount
    
    if old_remaining == new_remaining:
        return
    
    # Calculate utilization percentages
    old_utilization = ((old_instance.total_amount - old_remaining) / old_instance.total_amount * 100) if old_instance.total_amount > 0 else 0
    new_utilization = ((instance.total_amount - new_remaining) / instance.total_amount * 100) if instance.total_amount > 0 else 0
    
    logger.info(f"PO {instance.po_number}: Utilization changed from {old_utilization:.1f}% to {new_utilization:.1f}%")
    
    # Define thresholds
    thresholds = [50, 75, 90]
    
    for threshold in thresholds:
        # Check if we've crossed this threshold upward
        if old_utilization < threshold <= new_utilization:
            # Check if notification already exists for this threshold
            notification_exists = POBalanceNotification.objects.filter(
                purchase_order=instance, 
                threshold_percentage=threshold
            ).exists()
            
            if not notification_exists:
                # Create notification
                POBalanceNotification.objects.create(
                    purchase_order=instance,
                    threshold_percentage=threshold,
                    utilization_percentage=new_utilization,
                    remaining_balance=new_remaining,
                    created_at=timezone.now(),
                    is_read=False
                )
                logger.info(f"Created {threshold}% notification for PO {instance.po_number}")


@receiver(post_save, sender=PurchaseOrder)
def create_initial_notifications(sender, instance, created, **kwargs):
    """Create notifications for new POs that already have high utilization"""
    if created:
        remaining = instance.total_amount - instance.spent_amount
        utilization = ((instance.total_amount - remaining) / instance.total_amount * 100) if instance.total_amount > 0 else 0
        
        thresholds = [50, 75, 90]
        
        for threshold in thresholds:
            if utilization >= threshold:
                notification_exists = POBalanceNotification.objects.filter(
                    purchase_order=instance,
                    threshold_percentage=threshold
                ).exists()
                
                if not notification_exists:
                    POBalanceNotification.objects.create(
                        purchase_order=instance,
                        threshold_percentage=threshold,
                        utilization_percentage=utilization,
                        remaining_balance=remaining,
                        created_at=timezone.now(),
                        is_read=False
                    )
                    logger.info(f"Created initial {threshold}% notification for new PO {instance.po_number}")