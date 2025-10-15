from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import RateCard
from apps.customers.models import Customer

@login_required
def rate_card_list(request):
    rate_cards = RateCard.objects.select_related('customer').order_by('-created_at')
    
    # Filter by customer
    customer_filter = request.GET.get('customer')
    if customer_filter:
        rate_cards = rate_cards.filter(customer_id=customer_filter)
    
    # Pagination
    paginator = Paginator(rate_cards, 15)
    page_number = request.GET.get('page')
    rate_cards = paginator.get_page(page_number)
    
    customers = Customer.objects.filter(is_active=True).order_by('name')
    
    context = {
        'rate_cards': rate_cards,
        'customers': customers,
        'customer_filter': customer_filter,
    }
    return render(request, 'rate_cards/list.html', context)

@login_required
def create_rate_card(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        customer_id = request.POST.get('customer')
        description = request.POST.get('description')
        rate_per_unit = request.POST.get('rate_per_unit')
        unit_type = request.POST.get('unit_type')
        valid_from = request.POST.get('valid_from')
        valid_until = request.POST.get('valid_until')
        
        try:
            customer = Customer.objects.get(id=customer_id)
            
            rate_card = RateCard.objects.create(
                name=name,
                customer=customer,
                description=description,
                rate_per_unit=float(rate_per_unit),
                unit_type=unit_type,
                valid_from=valid_from,
                valid_until=valid_until,
                created_by=request.user
            )
            
            messages.success(request, 'Rate Card created successfully!')
            return redirect('rate_cards:list')
            
        except Exception as e:
            messages.error(request, f'Error creating rate card: {str(e)}')
    
    customers = Customer.objects.filter(is_active=True)
    
    context = {
        'customers': customers,
    }
    return render(request, 'rate_cards/create.html', context)