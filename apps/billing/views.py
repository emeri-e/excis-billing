from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils.dateformat import format
from .models import BillingRun
from apps.customers.models import Customer, Account
from apps.purchase_orders.models import PurchaseOrder
from apps.rate_cards.models import RateCard
from datetime import date, timedelta
import uuid

@login_required
def billing_run_list(request):
    billing_runs = BillingRun.objects.select_related(
        'customer', 'account', 'purchase_order', 'processed_by'
    ).order_by('-created_at')
    
    # Filter functionality
    status_filter = request.GET.get('status')
    customer_filter = request.GET.get('customer')
    
    if status_filter:
        billing_runs = billing_runs.filter(status=status_filter)
    
    if customer_filter:
        billing_runs = billing_runs.filter(customer_id=customer_filter)
    
    # Pagination
    paginator = Paginator(billing_runs, 20)
    page_number = request.GET.get('page')
    billing_runs = paginator.get_page(page_number)
    
    # Get customers for filter
    customers = Customer.objects.filter(is_active=True).order_by('name')
    
    context = {
        'billing_runs': billing_runs,
        'customers': customers,
        'status_filter': status_filter,
        'customer_filter': customer_filter,
        'status_choices': BillingRun.STATUS_CHOICES,
    }
    return render(request, 'billing/list.html', context)

@login_required
def create_billing_run_wizard(request):
    """Multi-step wizard for creating billing runs"""
    if request.method == 'POST':
        return handle_billing_run_creation(request)
    
    # GET request - show the wizard
    customers = Customer.objects.filter(is_active=True).order_by('name')
    today = date.today()
    
    # Calculate current and previous month for quick selection
    current_month = format(today, 'F Y')
    previous_month = format(today.replace(day=1) - timedelta(days=1), 'F Y')
    
    context = {
        'customers': customers,
        'current_month': current_month,
        'previous_month': previous_month,
    }
    
    return render(request, 'billing/create_wizard.html', context)

def handle_billing_run_creation(request):
    """Handle the form submission from the wizard"""
    try:
        customer_id = request.POST.get('customer_id')
        account_id = request.POST.get('account_id')
        period_type = request.POST.get('period_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        step = int(request.POST.get('step', 1))
        
        # Validate required fields
        if not customer_id or not account_id:
            return JsonResponse({'success': False, 'error': 'Customer and account are required'})
        
        customer = get_object_or_404(Customer, id=customer_id)
        account = get_object_or_404(Account, id=account_id)
        
        # Get active purchase order for the account
        active_po = account.purchase_orders.filter(status='active').first()
        if not active_po:
            return JsonResponse({'success': False, 'error': 'No active purchase order found for this account'})
        
        # Calculate billing period dates
        billing_start, billing_end = calculate_billing_period(period_type, start_date, end_date)
        
        # Generate unique run ID
        run_id = f"BR-{date.today().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # For now, create a basic billing run - in a full implementation,
        # you would process tickets, apply rates, etc.
        billing_amount = calculate_billing_amount(account, billing_start, billing_end)
        
        billing_run = BillingRun.objects.create(
            run_id=run_id,
            customer=customer,
            account=account,
            purchase_order=active_po,
            amount=billing_amount,
            billing_start_date=billing_start,
            billing_end_date=billing_end,
            processed_by=request.user,
            notes=f"Created via wizard - Period: {period_type}"
        )
        
        # Update PO remaining balance
        if active_po.remaining_balance >= billing_amount:
            active_po.remaining_balance -= billing_amount
            active_po.save()
            
            # Update account status
            account.update_status()
        else:
            return JsonResponse({
                'success': False, 
                'error': f'Insufficient PO balance. Available: {active_po.remaining_balance}, Required: {billing_amount}'
            })
        
        return JsonResponse({
            'success': True, 
            'billing_run_id': billing_run.id,
            'run_id': run_id,
            'message': 'Billing run created successfully!'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def calculate_billing_period(period_type, start_date=None, end_date=None):
    """Calculate billing period start and end dates"""
    today = date.today()
    
    if period_type == 'current_month':
        start_date = today.replace(day=1)
        next_month = start_date.replace(month=start_date.month + 1) if start_date.month < 12 else start_date.replace(year=start_date.year + 1, month=1)
        end_date = next_month - timedelta(days=1)
    elif period_type == 'previous_month':
        start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        end_date = today.replace(day=1) - timedelta(days=1)
    elif period_type == 'custom' and start_date and end_date:
        from datetime import datetime
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        # Default to current month
        start_date = today.replace(day=1)
        next_month = start_date.replace(month=start_date.month + 1) if start_date.month < 12 else start_date.replace(year=start_date.year + 1, month=1)
        end_date = next_month - timedelta(days=1)
    
    return start_date, end_date

def calculate_billing_amount(account, start_date, end_date):
    """Calculate billing amount for the account and period"""
    # This is a simplified calculation - in reality, you would:
    # 1. Import and process ticket data
    # 2. Apply rate cards
    # 3. Calculate based on actual work performed
    
    # For now, return a sample amount based on account's rate card
    rate_card = RateCard.objects.filter(customer=account.customer, is_active=True).first()
    if rate_card:
        # Simple calculation: rate * days in period
        days = (end_date - start_date).days + 1
        return float(rate_card.rate_per_unit * days)
    
    # Default sample amount
    return 5000.00

# API endpoints for AJAX calls
@login_required
def get_customer_accounts_api(request, customer_id):
    """API endpoint to get accounts for a customer"""
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        accounts = Account.objects.filter(customer=customer, is_active=True)
        
        accounts_data = []
        for account in accounts:
            accounts_data.append({
                'id': account.id,
                'account_id': account.account_id,
                'name': account.name,
                'billing_cycle': account.get_billing_cycle_display(),
                'currency': account.currency,
                'status': account.get_status_display(),
                'region': account.region.name if account.region else 'N/A',
            })
        
        return JsonResponse({'accounts': accounts_data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def get_account_details_api(request, account_id):
    """API endpoint to get detailed account information"""
    try:
        account = get_object_or_404(Account, id=account_id)
        active_po = account.active_purchase_order
        
        account_data = {
            'id': account.id,
            'account_id': account.account_id,
            'name': account.name,
            'billing_cycle': account.get_billing_cycle_display(),
            'currency': account.currency,
            'status': account.get_status_display(),
            'region': account.region.name if account.region else 'N/A',
            'active_po': active_po.po_number if active_po else None,
            'po_balance': str(active_po.remaining_balance) if active_po else None,
            'contact_email': account.contact_email,
            'contact_phone': account.contact_phone,
        }
        
        return JsonResponse(account_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def create_billing_run(request):
    """Legacy simple billing run creation (for backward compatibility)"""
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        account_id = request.POST.get('account') 
        po_id = request.POST.get('purchase_order')
        amount = request.POST.get('amount')
        billing_date = request.POST.get('billing_date')
        
        try:
            customer = Customer.objects.get(id=customer_id)
            account = Account.objects.get(id=account_id) if account_id else None
            po = PurchaseOrder.objects.get(id=po_id)
            
            # Generate unique run ID
            run_id = f"BR-{date.today().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            
            billing_run = BillingRun.objects.create(
                run_id=run_id,
                customer=customer,
                account=account,
                purchase_order=po,
                amount=float(amount),
                billing_date=billing_date,
                processed_by=request.user
            )
            
            # Update PO remaining balance
            po.remaining_balance -= float(amount)
            po.save()
            
            # Update account status if account is provided
            if account:
                account.update_status()
            
            messages.success(request, 'Billing Run created successfully!')
            return redirect('billing:list')
            
        except Exception as e:
            messages.error(request, f'Error creating billing run: {str(e)}')
    
    customers = Customer.objects.filter(is_active=True)
    accounts = Account.objects.filter(is_active=True)
    purchase_orders = PurchaseOrder.objects.filter(status='active')
    
    context = {
        'customers': customers,
        'accounts': accounts,
        'purchase_orders': purchase_orders,
    }
    return render(request, 'billing/create.html', context)