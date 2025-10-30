from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import RateCard, ServiceRate
from apps.customers.models import Customer
from django.apps import apps
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_http_methods

SVC_MODEL_MAP = {
    'service_rate': 'ServiceRate',
    'dedicated_rate': 'DedicatedRate',
    'scheduled_rate': 'ScheduledRate',
    'dispatch_rate': 'DispatchRate',
    'project_rate': 'ProjectRate'
}

def get_svc_model(svc_type):
    model_name = SVC_MODEL_MAP.get(svc_type)
    if not model_name:
        return None
    return apps.get_model('rate_cards', model_name)  

def svc_rate_to_dict(obj):
    return {
        'id': obj.id,
        'rate_card_id': obj.rate_card_id,
        'category': obj.category,
        'region': obj.region,
        'rate_type': obj.rate_type,
        'rate_value': float(obj.rate_value),
        'after_hours_multiplier': float(obj.after_hours_multiplier) if obj.after_hours_multiplier is not None else None,
        'weekend_multiplier': float(obj.weekend_multiplier) if obj.weekend_multiplier is not None else None,
        'travel_charge': float(obj.travel_charge),
        'remarks': obj.remarks,
        'created_at': obj.created_at.isoformat(),
        'updated_at': obj.updated_at.isoformat(),
    }

# list service-like entries for a ratecard (GET)
@require_http_methods(['GET'])
def svc_list_for_ratecard(request, pk, svc_type):
    Model = get_svc_model(svc_type)
    if not Model:
        return HttpResponseBadRequest("Unknown service type: {}".format(svc_type))
    rc = get_object_or_404(RateCard, pk=pk)
    qs = Model.objects.filter(rate_card=rc).order_by('id') 
    data = [svc_rate_to_dict(o) for o in qs]
    return JsonResponse({'results': data})

# create
@login_required
@require_http_methods(['POST'])
def svc_create(request, svc_type):
    Model = get_svc_model(svc_type)
    if not Model:
        return HttpResponseBadRequest("Unknown service type")
    rate_card_id = request.POST.get('rate_card_id')
    if not rate_card_id:
        return HttpResponseBadRequest("rate_card_id required")
    rc = get_object_or_404(RateCard, pk=rate_card_id)
    if not (request.user == rc.created_by or request.user.is_staff):
        return HttpResponseForbidden("Not allowed")
    obj = Model.objects.create(
        rate_card = rc,
        category = request.POST.get('category',''),
        region = request.POST.get('region',''),
        rate_type = request.POST.get('rate_type',''),
        rate_value = request.POST.get('rate_value') or 0,
        after_hours_multiplier = request.POST.get('after_hours_multiplier') or None,
        weekend_multiplier = request.POST.get('weekend_multiplier') or None,
        travel_charge = request.POST.get('travel_charge') or 0,
        remarks = request.POST.get('remarks',''),
        created_by = request.user
    )
    return JsonResponse({'success': True, svc_type: svc_rate_to_dict(obj)})

# update
@login_required
@require_http_methods(['POST'])
def svc_update(request, svc_type, pk):
    Model = get_svc_model(svc_type)
    if not Model:
        return HttpResponseBadRequest("Unknown service type")
    obj = get_object_or_404(Model, pk=pk)
    rc = obj.rate_card
    if not (request.user == rc.created_by or request.user.is_staff):
        return HttpResponseForbidden("Not allowed")
    obj.category = request.POST.get('category', obj.category)
    obj.region = request.POST.get('region', obj.region)
    obj.rate_type = request.POST.get('rate_type', obj.rate_type)
    if request.POST.get('rate_value') is not None:
        obj.rate_value = request.POST.get('rate_value')
    obj.after_hours_multiplier = request.POST.get('after_hours_multiplier') or obj.after_hours_multiplier
    obj.weekend_multiplier = request.POST.get('weekend_multiplier') or obj.weekend_multiplier
    obj.travel_charge = request.POST.get('travel_charge') or obj.travel_charge
    obj.remarks = request.POST.get('remarks', obj.remarks)
    obj.save()
    return JsonResponse({'success': True, svc_type: svc_rate_to_dict(obj)})

# delete
@login_required
@require_http_methods(['POST'])
def svc_delete(request, svc_type, pk):
    Model = get_svc_model(svc_type)
    if not Model:
        return HttpResponseBadRequest("Unknown service type")
    obj = get_object_or_404(Model, pk=pk)
    rc = obj.rate_card
    if not (request.user == rc.created_by or request.user.is_staff):
        return HttpResponseForbidden("Not allowed")
    obj.delete()
    return JsonResponse({'success': True})

@login_required
def rate_card_list(request):
    rate_cards = RateCard.objects.select_related('customer').order_by('-created_at')
    
    customer_filter = request.GET.get('customer')
    if customer_filter:
        rate_cards = rate_cards.filter(customer_id=customer_filter)

    # Pagination
    paginator = Paginator(rate_cards, 15)
    page_number = request.GET.get("page")
    rate_cards = paginator.get_page(page_number)

    customers = Customer.objects.filter(is_active=True).order_by("name")

    context = {
        "rate_cards": rate_cards,
        "customers": customers,
        "customer_filter": customer_filter,
    }
    return render(request, "rate_cards/list.html", context)


@login_required
def create_rate_card(request):
    if request.method == "POST":
        name = request.POST.get("name")
        customer_id = request.POST.get("customer")
        description = request.POST.get("description")
        rate_per_unit = request.POST.get("rate_per_unit")
        unit_type = request.POST.get("unit_type")
        valid_from = request.POST.get("valid_from")
        valid_until = request.POST.get("valid_until")

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
                created_by=request.user,
            )

            messages.success(request, "Rate Card created successfully!")
            return redirect("rate_cards:list")

        except Exception as e:
            messages.error(request, f"Error creating rate card: {str(e)}")

    customers = Customer.objects.filter(is_active=True)

    context = {
        "customers": customers,
    }
    return render(request, "rate_cards/create.html", context)



def ratecard_to_dict(r: RateCard):
    return {
        "id": r.id,
        "customer": r.customer.name,
        "customer_id": r.customer.id,
        "region": r.region,
        "country": r.country,
        "supplier": r.supplier,
        "currency": r.currency,
        "entity": r.entity,
        "payment": r.payment_terms,
        "status": r.status,
        "created_by": r.created_by.username if r.created_by else None,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


def service_rate_to_dict(s: ServiceRate):
    return {
        "id": s.id,
        "rate_card_id": s.rate_card_id,
        "category": s.category,
        "region": s.region,
        "rate_type": s.rate_type,
        "rate_value": float(s.rate_value),
        "after_hours_multiplier": (
            float(s.after_hours_multiplier)
            if s.after_hours_multiplier is not None
            else None
        ),
        "weekend_multiplier": (
            float(s.weekend_multiplier) if s.weekend_multiplier is not None else None
        ),
        "travel_charge": float(s.travel_charge),
        "remarks": s.remarks,
    }


@require_http_methods(["GET"])
def ratecard_list(request):
    qs = RateCard.objects.select_related('customer','created_by').all().order_by('-updated_at')
    data = [ratecard_to_dict(r) for r in qs]
    return JsonResponse({"results": data})


@login_required
@require_http_methods(["POST"])
def ratecard_create(request):
    cust_name = request.POST.get('customer') or request.POST.get('customer_name')
    if not cust_name:
        return HttpResponseBadRequest("customer is required")
    customer, _ = Customer.objects.get_or_create(name=cust_name)
    r = RateCard.objects.create(
        customer=customer,
        created_by=request.user,
        region=request.POST.get("region", ""),
        country=request.POST.get("country", ""),
        supplier=request.POST.get("supplier", ""),
        currency=request.POST.get("currency", "USD"),
        entity=request.POST.get("entity", ""),
        payment_terms=request.POST.get("payment", ""),
        status=request.POST.get("status", "Active"),
    )
    return JsonResponse({"success": True, "ratecard": ratecard_to_dict(r)})


@require_http_methods(["GET"])
def ratecard_detail(request, pk):
    r = get_object_or_404(RateCard, pk=pk)
    data = ratecard_to_dict(r)
    data['service_rates'] = [service_rate_to_dict(s) for s in r.service_rates.all()]
    return JsonResponse({'ratecard': data})

@login_required
@require_http_methods(["POST"])
def ratecard_update(request, pk):
    r = get_object_or_404(RateCard, pk=pk)
    if not (request.user == r.created_by or request.user.is_staff):
        return HttpResponseForbidden("Not allowed")

    customer_name = request.POST.get('customer')
    if customer_name:
        customer, _ = Customer.objects.get_or_create(name=customer_name)
        r.customer = customer
    r.region = request.POST.get("region", r.region)
    r.country = request.POST.get("country", r.country)
    r.supplier = request.POST.get("supplier", r.supplier)
    r.currency = request.POST.get("currency", r.currency)
    r.entity = request.POST.get("entity", r.entity)
    r.payment_terms = request.POST.get("payment", r.payment_terms)
    r.status = request.POST.get("status", r.status)
    r.save()
    return JsonResponse({"success": True, "ratecard": ratecard_to_dict(r)})


@login_required
@require_http_methods(["POST"])
def ratecard_delete(request, pk):
    r = get_object_or_404(RateCard, pk=pk)
    if not (request.user == r.created_by or request.user.is_staff):
        return HttpResponseForbidden("Not allowed")
    r.delete()
    return JsonResponse({"success": True})


# ServiceRate endpoints
@login_required
@require_http_methods(["POST"])
def service_rate_create(request):
    rate_card_id = request.POST.get("rate_card_id")
    if not rate_card_id:
        return HttpResponseBadRequest("rate_card_id required")
    rc = get_object_or_404(RateCard, pk=rate_card_id)
    if not (request.user == rc.created_by or request.user.is_staff):
        return HttpResponseForbidden("Not allowed")
    s = ServiceRate.objects.create(
        rate_card=rc,
        category=request.POST.get("category", ""),
        region=request.POST.get("region", ""),
        rate_type=request.POST.get("rate_type", "hourly"),
        rate_value=request.POST.get("rate_value") or 0,
        after_hours_multiplier=request.POST.get("after_hours_multiplier") or None,
        weekend_multiplier=request.POST.get("weekend_multiplier") or None,
        travel_charge=request.POST.get("travel_charge") or 0,
        remarks=request.POST.get("remarks", ""),
    )
    return JsonResponse({"success": True, "service_rate": service_rate_to_dict(s)})


@require_http_methods(["GET"])
def service_rates_for_ratecard(request, pk):
    rc = get_object_or_404(RateCard, pk=pk)
    data = [service_rate_to_dict(s) for s in rc.service_rates.all()]
    return JsonResponse({"results": data})


@login_required
@require_http_methods(["POST"])
def service_rate_update(request, pk):
    s = get_object_or_404(ServiceRate, pk=pk)
    rc = s.rate_card
    if not (request.user == rc.created_by or request.user.is_staff):
        return HttpResponseForbidden("Not allowed")
    s.category = request.POST.get("category", s.category)
    s.region = request.POST.get("region", s.region)
    s.rate_type = request.POST.get("rate_type", s.rate_type)
    if request.POST.get("rate_value") is not None:
        s.rate_value = request.POST.get("rate_value")
    s.after_hours_multiplier = (
        request.POST.get("after_hours_multiplier") or s.after_hours_multiplier
    )
    s.weekend_multiplier = (
        request.POST.get("weekend_multiplier") or s.weekend_multiplier
    )
    s.travel_charge = request.POST.get("travel_charge") or s.travel_charge
    s.remarks = request.POST.get("remarks", s.remarks)
    s.save()
    return JsonResponse({"success": True, "service_rate": service_rate_to_dict(s)})


@login_required
@require_http_methods(["POST"])
def service_rate_delete(request, pk):
    s = get_object_or_404(ServiceRate, pk=pk)
    rc = s.rate_card
    if not (request.user == rc.created_by or request.user.is_staff):
        return HttpResponseForbidden("Not allowed")
    s.delete()
    return JsonResponse({"success": True})


