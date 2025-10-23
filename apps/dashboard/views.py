from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, Q, ExpressionWrapper, DecimalField
from apps.purchase_orders.models import PurchaseOrder
from apps.billing.models import BillingRun
from apps.customers.models import Customer
from datetime import date, timedelta

@login_required
def dashboard_home(request):
    # Calculate dashboard KPIs
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    
    # Basic counts
    total_customers = Customer.objects.filter(is_active=True).count()
    active_pos = PurchaseOrder.objects.filter(status='active').count()
    
    # Revenue calculation (last 30 days)
    total_revenue = BillingRun.objects.filter(
        status='completed',
        billing_date__gte=thirty_days_ago
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Pending approvals
    pending_approvals = BillingRun.objects.filter(status='pending').count()
    
    # Low balance POs (less than 20% remaining)
    # remaining_balance = total_amount - spent_amount
    # utilization = (spent_amount / total_amount) * 100
    low_balance_pos = PurchaseOrder.objects.filter(
        status='active',
        total_amount__gt=F('spent_amount')  # Has remaining balance
    ).annotate(
        utilization_percent=(F('spent_amount') / F('total_amount')) * 100
    ).filter(utilization_percent__gte=80).count()
    
    # Draft POs
    draft_pos = PurchaseOrder.objects.filter(status='draft').count()
    
    # Calculate total PO value (active POs only)
    total_po_value = PurchaseOrder.objects.filter(
        status='active'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    kpis = {
        'total_customers': total_customers,
        'active_pos': active_pos,
        'total_revenue': float(total_revenue),
        'pending_approvals': pending_approvals,
        'low_balance_pos': low_balance_pos,
        'draft_pos': draft_pos,
        'total_po_value': float(total_po_value),
    }
    
    # Recent billing runs (last 10)
    recent_billing = BillingRun.objects.select_related(
        'customer', 
        'purchase_order'
    ).order_by('-created_at')[:10]
    
    # Recent POs (last 5)
    recent_pos = PurchaseOrder.objects.select_related(
        'customer'
    ).order_by('-created_at')[:5]
    
    # Low balance PO details for alerts
    low_balance_pos_details = PurchaseOrder.objects.filter(
        status='active',
        total_amount__gt=F('spent_amount')  # Has remaining balance
    ).annotate(
        utilization_percent=(F('spent_amount') / F('total_amount')) * 100,
        remaining_balance=ExpressionWrapper(
            F('total_amount') - F('spent_amount'),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )
    ).filter(utilization_percent__gte=80).select_related('customer')[:5]
    
    # Expiring POs (expiring in next 30 days)
    expiring_soon = PurchaseOrder.objects.filter(
        valid_until__lte=today + timedelta(days=30),
        valid_until__gt=today,
        status='active'
    ).count()
    
    context = {
        'kpis': kpis,
        'recent_billing': recent_billing,
        'recent_pos': recent_pos,
        'low_balance_pos_details': low_balance_pos_details,
        'expiring_soon': expiring_soon,
    }
    return render(request, 'dashboard/home.html', context)