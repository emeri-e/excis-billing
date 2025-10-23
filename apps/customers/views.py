import logging
import json
from datetime import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from decimal import Decimal

from apps.billing.models import BillingRun
from .models import Customer, Account, BillingCycle, Project, Currency, Country
from .forms import CustomerForm, AccountForm, ProjectForm, BillingCycleForm, CurrencyForm, CountryForm

# Create logger
logger = logging.getLogger('customers')

@login_required
def get_customer_accounts_api(request, customer_id):
    """Get all accounts for a customer"""
    try:
        accounts = Account.objects.filter(
            customer_id=customer_id,
            is_active=True
        ).order_by('name')
        
        account_data = [
            {
                'id': account.id,
                'name': account.name,
                'account_id': account.account_id,
            }
            for account in accounts
        ]
        
        return JsonResponse({
            'success': True,
            'accounts': account_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def customer_accounts_list(request):
    """Fixed customer & accounts management page"""
    
    logger.info("Starting customer_accounts_list view")
    
    # Initialize default context for error handling
    default_context = {
        'customers': Customer.objects.none(),
        'billing_cycles': BillingCycle.objects.none(),
        'customers_json': '[]',
        'accounts_json': '[]',
        'debug_accounts_count': 0,
    }
    
    try:
        # Step 1: Get customers
        customers = Customer.objects.filter(is_active=True).order_by('name')
        customers_count = customers.count()
        logger.info(f"Found {customers_count} active customers")
        
        # Step 2: Get accounts with proper select_related
        accounts = Account.objects.select_related(
            'customer', 'billing_cycle', 'project', 'currency', 'country'
        ).filter(is_active=True).order_by('customer__name', 'name')
        accounts_count = accounts.count()
        logger.info(f"Found {accounts_count} active accounts")
        
        # Step 3: Get billing cycles
        billing_cycles = BillingCycle.objects.filter(is_active=True).order_by('name')
        logger.info(f"Found {billing_cycles.count()} billing cycles")
        
        # Step 4: Build customers JSON safely
        customers_data = []
        for customer in customers:
            try:
                # Get account count safely
                account_count = customer.accounts.filter(is_active=True).count()
                
                customer_dict = {
                    'id': customer.id,
                    'name': str(customer.name),
                    'code': str(customer.code or ''),
                    'account_count': account_count
                }
                customers_data.append(customer_dict)
                logger.debug(f"Added customer {customer.id}: {customer.name} ({account_count} accounts)")
                
            except Exception as e:
                logger.error(f"Error processing customer {customer.id}: {e}")
                continue
        
        # Step 5: Build accounts JSON safely
        accounts_data = []
        for account in accounts:
            try:
                customer_id = account.customer.id if account.customer else None
                if not customer_id:
                    logger.warning(f"Account {account.id} has no customer - skipping")
                    continue
                
                # Safely get related field data
                region_name = account.region if account.region else None
                billing_cycle_name = account.billing_cycle.name if account.billing_cycle else None
                billing_cycle_id = account.billing_cycle.id if account.billing_cycle else None
                currency_code = account.currency.code if account.currency else 'USD'
                
                # Handle purchase order data safely
                active_po_number = None
                try:
                    if hasattr(account, 'active_purchase_order') and account.active_purchase_order:
                        active_po_number = str(account.active_purchase_order.po_number)
                except Exception as e:
                    logger.debug(f"Could not get PO for account {account.id}: {e}")
                
                # Handle balance safely
                po_balance = None
                try:
                    if hasattr(account, 'po_balance') and account.po_balance is not None:
                        po_balance = str(account.po_balance)
                except Exception as e:
                    logger.debug(f"Could not get balance for account {account.id}: {e}")
                
                # Handle last billing run safely
                last_billing_run = None
                try:
                    if hasattr(account, 'last_billing_run') and account.last_billing_run:
                        last_billing_run = account.last_billing_run.strftime('%b %d, %Y')
                except Exception as e:
                    logger.debug(f"Could not get billing run for account {account.id}: {e}")
                
                account_dict = {
                    'id': account.id,
                    'customer_id': customer_id,
                    'name': str(account.name or ''),
                    'account_id': str(getattr(account, 'account_id', '') or ''),
                    'region_name': str(region_name) if region_name else None,
                    'billing_cycle_name': str(billing_cycle_name) if billing_cycle_name else None,
                    'billing_cycle_id': billing_cycle_id,
                    'currency': str(currency_code),
                    'active_po_number': active_po_number,
                    'po_balance': po_balance,
                    'last_billing_run': last_billing_run,
                    'status': str(getattr(account, 'status', 'unknown') or 'unknown')
                }
                
                accounts_data.append(account_dict)
                logger.debug(f"Added account {account.id}: {account.name} for customer {customer_id}")
                
            except Exception as e:
                logger.error(f"Error processing account {account.id}: {e}")
                continue
        
        # Step 6: Serialize to JSON safely
        try:
            customers_json = json.dumps(customers_data, ensure_ascii=False, indent=None)
            logger.info(f"Created customers JSON: {len(customers_json)} characters")
        except Exception as e:
            logger.error(f"Failed to serialize customers JSON: {e}")
            customers_json = json.dumps([])
        
        try:
            accounts_json = json.dumps(accounts_data, ensure_ascii=False, indent=None)
            logger.info(f"Created accounts JSON: {len(accounts_json)} characters")
        except Exception as e:
            logger.error(f"Failed to serialize accounts JSON: {e}")
            accounts_json = json.dumps([])
        
        # Step 7: Build final context
        context = {
            'customers': customers,
            'billing_cycles': billing_cycles,
            'customers_json': customers_json,
            'accounts_json': accounts_json,
            'debug_accounts_count': len(accounts_data),
        }
        
        logger.info(f"View completed successfully - {len(customers_data)} customers, {len(accounts_data)} accounts")
        return render(request, 'customers/list.html', context)
        
    except Exception as e:
        logger.error(f"Critical error in customer_accounts_list: {e}", exc_info=True)
        
        error_context = default_context.copy()
        error_context['error_message'] = f"Error loading data: {str(e)}"
        
        return render(request, 'customers/list.html', error_context)


@login_required
def customer_list(request):
    """Simple customer list view"""
    customers = Customer.objects.filter(is_active=True).order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(customers, 10)
    page_number = request.GET.get('page')
    customers = paginator.get_page(page_number)
    
    context = {
        'customers': customers,
        'search_query': search_query,
    }
    return render(request, 'customers/list.html', context)


@login_required
def create_customer(request):
    """Create customer with initial project"""
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            # Save customer
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.save()
            
            # Create initial project
            project = Project.objects.create(
                customer=customer,
                name=form.cleaned_data['project_name'],
                code=form.cleaned_data['project_code'],
                description=form.cleaned_data.get('project_description', ''),
                created_by=request.user
            )
            
            messages.success(
                request, 
                f'Customer "{customer.name}" and project "{project.name}" created successfully!'
            )
            return redirect('customers:detail', pk=customer.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomerForm()
    
    return render(request, 'customers/create.html', {'form': form})


@login_required
def create_account(request):
    """Create a new account with customer and project association"""
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.created_by = request.user
            account.save()
            messages.success(request, f'Account "{account.name}" created successfully!')
            return redirect('customers:account_detail', pk=account.id)
        else:
            logger.debug(f"Form errors: {form.errors}")
            messages.error(request, 'Please correct the errors below.')
    else:
        initial = {}
        customer_id = request.GET.get('customer')
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id, is_active=True)
                initial['customer'] = customer  # pass the instance, not just the ID
                logger.debug(f"Pre-selected customer {customer_id} ({customer.name})")
            except Customer.DoesNotExist:
                logger.warning(f"Customer ID {customer_id} not found")
        form = AccountForm(initial=initial)
    
    context = {
        'form': form,
        'currencies': Currency.objects.filter(is_active=True),
        'countries': Country.objects.filter(is_active=True)
    }
    return render(request, 'customers/create_account.html', context)

@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    
    # Get accounts for this customer
    accounts = customer.accounts.filter(is_active=True).select_related(
        'billing_cycle', 'project', 'currency', 'country'
    ).order_by('-created_at')
    
    # Get projects for this customer
    projects = customer.projects.filter(is_active=True).order_by('-created_at')
    
    # Get purchase orders for this customer (if the relationship exists)
    purchase_orders = []
    try:
        purchase_orders = customer.purchase_orders.all().order_by('-created_at')[:10]
    except AttributeError:
        logger.debug(f"Customer {customer.id} has no purchase_orders relationship")
    
    context = {
        'customer': customer,
        'accounts': accounts,
        'projects': projects,
        'purchase_orders': purchase_orders,
    }
    return render(request, 'customers/detail.html', context)


@login_required
def account_detail(request, pk):
    """Detail view for a specific account"""
    account = get_object_or_404(Account.objects.select_related(
        'customer', 'billing_cycle', 'project', 'currency', 'country'
    ), pk=pk)
    
    # Get purchase orders for this account (if relationship exists)
    purchase_orders = []
    try:
        purchase_orders = account.purchase_orders.all().order_by('-created_at')
    except AttributeError:
        logger.debug(f"Account {account.id} has no purchase_orders relationship")
    
    # Get billing history for this account
    billing_history = []
    try:
        billing_history = BillingRun.objects.filter(
            account=account
        ).select_related('purchase_order').order_by('-created_at')[:10]
    except Exception as e:
        logger.debug(f"Could not get billing history for account {account.id}: {e}")
    
    # Get account metrics safely
    metrics = {}
    try:
        if hasattr(account, 'active_pos_count'):
            metrics['active_pos_count'] = account.active_pos_count
        if hasattr(account, 'total_po_value'):
            metrics['total_po_value'] = account.total_po_value
        if hasattr(account, 'remaining_balance'):
            metrics['remaining_balance'] = account.remaining_balance
    except Exception as e:
        logger.debug(f"Could not get metrics for account {account.id}: {e}")
    
    context = {
        'account': account,
        'purchase_orders': purchase_orders,
        'billing_history': billing_history,
        **metrics
    }
    return render(request, 'customers/account_detail.html', context)


@login_required
def edit_customer(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.save()
            messages.success(request, f'Customer {customer.name} updated successfully!')
            return redirect('customers:detail', pk=customer.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomerForm(instance=customer)
    
    context = {
        'customer': customer,
        'form': form,
        'days_since_created': (timezone.now() - customer.created_at).days if hasattr(customer.created_at, 'tzinfo') else 0
    }
    return render(request, 'customers/edit.html', context)


@login_required
def delete_customer(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer_name = customer.name
        customer.delete()
        messages.success(request, f'Customer {customer_name} deleted successfully!')
        return redirect('customers:list')
    return redirect('customers:detail', pk=pk)


# AJAX Endpoints
@login_required
def load_projects(request):
    """AJAX endpoint to load projects based on customer selection"""
    customer_id = request.GET.get('customer_id')
    projects = Project.objects.filter(
        customer_id=customer_id, 
        is_active=True
    ).order_by('name')
    
    return JsonResponse({
        'projects': list(projects.values('id', 'name', 'code'))
    })


@login_required
def load_accounts(request):
    """AJAX endpoint to load accounts based on customer selection"""
    customer_id = request.GET.get('customer_id')
    accounts = Account.objects.filter(
        customer_id=customer_id,
        is_active=True
    ).order_by('name')
    
    return JsonResponse({
        'accounts': list(accounts.values('id', 'name', 'account_id'))
    })


# Billing Cycle Management
@login_required
def billing_cycles_list(request):
    """List all billing cycles"""
    billing_cycles = BillingCycle.objects.filter(is_active=True).select_related(
        'customer', 'account', 'project'
    ).order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        billing_cycles = billing_cycles.filter(
            Q(name__icontains=search_query) |
            Q(customer__name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(billing_cycles, 15)
    page_number = request.GET.get('page')
    billing_cycles = paginator.get_page(page_number)
    
    context = {
        'billing_cycles': billing_cycles,
        'search_query': search_query,
    }
    return render(request, 'customers/billing_cycles_list.html', context)


@login_required
def create_billing_cycle(request):
    """Create billing cycle with customer, account, and project association"""
    if request.method == 'POST':
        form = BillingCycleForm(request.POST)
        if form.is_valid():
            billing_cycle = form.save()
            messages.success(request, f'Billing cycle "{billing_cycle.name}" created successfully!')
            return redirect('customers:billing_cycles_list')
    else:
        form = BillingCycleForm()
        
        # Pre-populate if parameters provided
        customer_id = request.GET.get('customer')
        if customer_id:
            form.fields['customer'].initial = customer_id
    
    return render(request, 'customers/create_billing_cycle.html', {'form': form})


# Currency Management
@login_required
def manage_currencies(request):
    """Manage currencies"""
    if request.method == 'POST':
        form = CurrencyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Currency added successfully!')
            return redirect('customers:manage_currencies')
    else:
        form = CurrencyForm()
    
    currencies = Currency.objects.filter(is_active=True).order_by('code')
    context = {
        'form': form,
        'currencies': currencies
    }
    return render(request, 'customers/manage_currencies.html', context)


# Country Management
@login_required
def manage_countries(request):
    """Manage countries"""
    if request.method == 'POST':
        form = CountryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Country added successfully!')
            return redirect('customers:manage_countries')
    else:
        form = CountryForm()
    
    countries = Country.objects.filter(is_active=True).order_by('name')
    context = {
        'form': form,
        'countries': countries
    }
    return render(request, 'customers/manage_countries.html', context)