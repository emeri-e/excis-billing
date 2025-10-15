import json
import PyPDF2
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_protect
from datetime import date, timedelta
import csv
import logging

from .models import PurchaseOrder, POBalanceNotification, PurchaseOrderPDF
from .forms import PurchaseOrderEditForm, PurchaseOrderForm, PurchaseOrderPDFUploadForm
from apps.customers.models import Customer, Account

# Configure logging
logger = logging.getLogger(__name__)

@login_required
def purchase_order_list(request):
    """Enhanced purchase order list with KPIs and filtering"""
    pos = PurchaseOrder.objects.select_related('customer', 'account').order_by('-created_at')
    
    # Get filter parameters
    status_filter = request.GET.get('status')
    customer_filter = request.GET.get('customer')
    account_filter = request.GET.get('account')
    search_query = request.GET.get('search')
    
    # Apply filters
    if status_filter:
        pos = pos.filter(status=status_filter)
    
    if customer_filter:
        pos = pos.filter(customer_id=customer_filter)
    
    if account_filter:
        pos = pos.filter(account_id=account_filter)
        
    if search_query:
        pos = pos.filter(
            Q(po_number__icontains=search_query) |
            Q(customer__name__icontains=search_query) |
            Q(customer__code__icontains=search_query)
        )
    
    # Calculate KPIs
    all_pos = PurchaseOrder.objects.all()
    today = date.today()
    
    kpis = {
        'active_pos': all_pos.filter(status='active').count(),
        'total_value': all_pos.filter(status__in=['active', 'expiring_soon']).aggregate(
            total=Sum('total_amount'))['total'] or 0,
        'low_balance_pos': all_pos.filter(
            remaining_balance__lt=F('total_amount') * 0.2,
            status='active'
        ).count(),
        'expiring_soon': all_pos.filter(
            valid_until__lte=today + timedelta(days=30),
            valid_until__gt=today,
            status__in=['active', 'expiring_soon']
        ).count(),
    }
    
    # Get unread notification count for the current user
    unread_notifications = POBalanceNotification.objects.filter(
        is_read=False,
        purchase_order__created_by=request.user
    ).count()

    all_notifications = POBalanceNotification.objects.all()
    unread_all = POBalanceNotification.objects.filter(is_read=False)
    
    logger.debug(f"Total notifications: {all_notifications.count()}")
    logger.debug(f"Unread notifications: {unread_all.count()}")
    
    # Store total count before pagination
    total_count = pos.count()
    
    # Pagination
    paginator = Paginator(pos, 15)
    page_number = request.GET.get('page')
    pos = paginator.get_page(page_number)
    
    # Get filter options
    customers = Customer.objects.filter(is_active=True).order_by('name')
    accounts = Account.objects.filter(is_active=True).select_related('customer').order_by('customer__name', 'name')
    
    context = {
        'purchase_orders': pos,
        'kpis': kpis,
        'customers': customers,
        'accounts': accounts,
        'status_filter': status_filter,
        'customer_filter': customer_filter,
        'account_filter': account_filter,
        'search_query': search_query,
        'status_choices': PurchaseOrder.STATUS_CHOICES,
        'total_count': total_count,
        'unread_notifications': unread_notifications,
    }
    return render(request, 'purchase_orders/list.html', context)

@login_required
def create_purchase_order(request):
    """Create a new purchase order with PDF upload support and proper session handling"""
    
    # Get PDF data from session - ensure it persists
    pdf_data = request.session.get('extracted_pdf_data')
    pdf_form = PurchaseOrderPDFUploadForm()
    
    logger.debug(f"create_purchase_order: Session PDF data exists: {pdf_data is not None}")
    if pdf_data:
        logger.debug(f"create_purchase_order: PDF data keys: {list(pdf_data.keys())}")
    
    if request.method == 'POST':        
        # Handle PDF upload
        if 'upload_pdf' in request.POST:
            pdf_form = PurchaseOrderPDFUploadForm(request.POST, request.FILES)
            
            if pdf_form.is_valid():
                try:
                    pdf_file = pdf_form.cleaned_data['pdf_file']
                    
                    # Create PDF upload instance
                    pdf_upload = PurchaseOrderPDF(
                        pdf_file=pdf_file,
                        original_filename=pdf_file.name,
                        uploaded_by=request.user
                    )
                    pdf_upload.save()
                    
                    extracted_data = pdf_upload.extract_pdf_data()
                    
                    logger.info(f"PDF extraction completed. Success: {pdf_upload.extraction_success}")
                    logger.info(f"Extracted data: {extracted_data}")
                    
                    if extracted_data and pdf_upload.extraction_success:
                        # Try to match customer from supplier name
                        matched_customer = None
                        if 'supplier' in extracted_data and extracted_data['supplier']:
                            supplier_name = extracted_data['supplier'].strip()
                            logger.info(f"Attempting to match customer with supplier: {supplier_name}")
                            
                            # Try exact match first
                            try:
                                matched_customer = Customer.objects.get(
                                    name__iexact=supplier_name,
                                    is_active=True
                                )
                                logger.info(f"✓ Exact customer match found: {matched_customer.name}")
                            except Customer.DoesNotExist:
                                # Try partial match
                                matched_customers = Customer.objects.filter(
                                    name__icontains=supplier_name[:20],  # Use first 20 chars
                                    is_active=True
                                )
                                if matched_customers.count() == 1:
                                    matched_customer = matched_customers.first()
                                    logger.info(f"✓ Partial customer match found: {matched_customer.name}")
                                elif matched_customers.count() > 1:
                                    logger.warning(f"Multiple customer matches found for '{supplier_name}', not auto-selecting")
                                else:
                                    logger.warning(f"No customer match found for '{supplier_name}'")
                            except Customer.MultipleObjectsReturned:
                                logger.warning(f"Multiple exact matches found for '{supplier_name}'")
                        
                        # Add matched customer to extracted data
                        if matched_customer:
                            extracted_data['matched_customer_id'] = matched_customer.id
                            extracted_data['matched_customer_name'] = matched_customer.name
                        
                        # Store PDF data in session with explicit save
                        request.session['current_pdf_upload_id'] = pdf_upload.id
                        request.session['extracted_pdf_data'] = extracted_data
                        request.session.modified = True
                        
                        # Force session save
                        request.session.save()
                        
                        logger.info(f"Stored PDF data in session. Keys: {list(extracted_data.keys())}")

                        # Build success message
                        extracted_fields = []
                        if extracted_data.get('reference_number'):
                            extracted_fields.append(f"Order: {extracted_data['reference_number']}")
                        if extracted_data.get('currency') and extracted_data.get('total_amount'):
                            extracted_fields.append(f"{extracted_data['currency']} {extracted_data['total_amount']:,.2f}")
                        if extracted_data.get('valid_from'):
                            extracted_fields.append(f"From: {extracted_data['valid_from']}")
                        if extracted_data.get('valid_until'):
                            extracted_fields.append(f"Until: {extracted_data['valid_until']}")
                        if extracted_data.get('supplier'):
                            supplier_short = extracted_data['supplier'][:20] + "..." if len(extracted_data['supplier']) > 20 else extracted_data['supplier']
                            extracted_fields.append(f"Supplier: {supplier_short}")
                        if matched_customer:
                            extracted_fields.append(f"Matched Customer: {matched_customer.name}")
                        
                        if extracted_fields:
                            success_msg = f"PDF processed successfully! Extracted: {', '.join(extracted_fields)}"
                            messages.success(request, success_msg)
                        else:
                            warning_msg = "PDF uploaded but no data could be extracted."
                            messages.warning(request, warning_msg)
                            logger.warning(warning_msg)
                    
                    else:
                        error_msg = f"PDF extraction failed: {pdf_upload.extraction_errors}"
                        messages.error(request, error_msg)
                        logger.error(error_msg)
                    
                    # Redirect to same page to show results
                    return redirect('purchase_orders:create')
                
                except Exception as e:
                    error_msg = f"Error processing PDF: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    messages.error(request, error_msg)
                    
                    # Clean up session on error
                    for key in ['current_pdf_upload_id', 'extracted_pdf_data']:
                        request.session.pop(key, None)
                    request.session.modified = True
                    request.session.save()
            
            else:
                logger.error(f"PDF form validation failed: {pdf_form.errors}")
                for field, errors in pdf_form.errors.items():
                    for error in errors:
                        messages.error(request, f"PDF Upload - {field}: {error}")
        
        # Handle PO creation
        elif 'create_po' in request.POST:            
            form = PurchaseOrderForm(request.POST, pdf_data=pdf_data)
            
            if form.is_valid():
                po = form.save(commit=False)
                po.created_by = request.user
                po.status = 'active' if request.POST.get('create_po') == 'active' else 'draft'
                po.save()
                
                # Associate PDF with PO if available
                pdf_upload_id = request.session.get('current_pdf_upload_id')
                if pdf_upload_id:
                    try:
                        pdf_upload = PurchaseOrderPDF.objects.get(id=pdf_upload_id)
                        pdf_upload.purchase_order = po
                        pdf_upload.save()
                        logger.info(f"Associated PDF upload {pdf_upload_id} with PO {po.po_number}")
                    except PurchaseOrderPDF.DoesNotExist:
                        logger.warning(f"PDF upload {pdf_upload_id} not found")
                
                # Clear session data after successful creation
                for key in ['current_pdf_upload_id', 'extracted_pdf_data']:
                    request.session.pop(key, None)
                request.session.modified = True
                request.session.save()
                
                messages.success(request, f"Purchase Order {po.po_number} created successfully! Status: {po.get_status_display()}")
                return redirect('purchase_orders:list')
            
            else:
                logger.error(f"PO form validation failed: {form.errors}")
                for field, errors in form.errors.items():
                    field_name = field.replace('_', ' ').title()
                    for error in errors:
                        messages.error(request, f"{field_name}: {error}")
    
    # Re-fetch PDF data in case it was just stored
    current_pdf_data = request.session.get('extracted_pdf_data')
    
    # Prepare initial form data
    form_initial = {}
    matched_customer_id = None
    
    if current_pdf_data:
        logger.info(f"Preparing form with PDF data. Keys: {list(current_pdf_data.keys())}")
        
        # Get matched customer if available
        if 'matched_customer_id' in current_pdf_data:
            matched_customer_id = current_pdf_data['matched_customer_id']
            form_initial['customer'] = matched_customer_id
            logger.info(f"Setting initial customer to: {matched_customer_id}")
        
        # Map PDF fields to form fields
        field_mapping = {
            'reference_number': 'reference_number',
            'currency': 'currency', 
            'total_amount': 'total_amount',
            'valid_from': 'valid_from',
            'valid_until': 'valid_until',
        }
        
        for pdf_field, form_field in field_mapping.items():
            if pdf_field in current_pdf_data and current_pdf_data[pdf_field]:
                form_initial[form_field] = current_pdf_data[pdf_field]
                logger.debug(f"Mapping {pdf_field} -> {form_field}: {current_pdf_data[pdf_field]}")
        
        # Calculate balance from total and invoiced
        if 'total_amount' in current_pdf_data:
            if 'total_invoiced' in current_pdf_data and current_pdf_data['total_invoiced']:
                try:
                    total = float(str(current_pdf_data['total_amount']).replace(',', ''))
                    invoiced = float(str(current_pdf_data['total_invoiced']).replace(',', ''))
                    form_initial['balance'] = max(0, total - invoiced)
                    logger.info(f"Calculated balance: {form_initial['balance']} (Total: {total} - Invoiced: {invoiced})")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error calculating balance: {e}")
                    form_initial['balance'] = current_pdf_data['total_amount']
            else:
                form_initial['balance'] = current_pdf_data['total_amount']
        
        form = PurchaseOrderForm(initial=form_initial, pdf_data=current_pdf_data)
    else:
        # Default initialization
        today = date.today()
        form = PurchaseOrderForm(initial={
            'valid_from': today,
            'valid_until': today + timedelta(days=365),
            'currency': 'USD',
            'balance': 0,
        })
    
    # Prepare template context with debugging
    template_pdf_data = {}
    if current_pdf_data:
        for key, value in current_pdf_data.items():
            try:
                if isinstance(value, (str, int, float, bool, type(None))):
                    template_pdf_data[key] = value
                else:
                    template_pdf_data[key] = str(value)
            except Exception as e:
                logger.warning(f"Error converting PDF data field {key}: {e}")
                template_pdf_data[key] = str(value) if value is not None else ''
    
    context = {
        'pdf_form': pdf_form,
        'form': form,
        'pdf_data': template_pdf_data,
        'has_pdf_data': bool(template_pdf_data),
        'pdf_data_json': json.dumps(template_pdf_data) if template_pdf_data else '{}',
        'matched_customer_id': matched_customer_id,
        'debug_info': {
            'session_has_pdf_data': current_pdf_data is not None,
            'pdf_data_keys': list(template_pdf_data.keys()) if template_pdf_data else [],
            'session_keys': list(request.session.keys()),
            'form_initial_keys': list(form_initial.keys()) if form_initial else [],
        } if request.user.is_superuser else None,
    }
    
    logger.info(f"Rendering create template. Has PDF data: {bool(template_pdf_data)}, Matched customer: {matched_customer_id}")
    
    return render(request, 'purchase_orders/create.html', context)


@login_required
def purchase_order_detail(request, pk):
    """Detailed view of a purchase order"""
    po = get_object_or_404(PurchaseOrder, pk=pk)
    billing_runs = po.billingrun_set.all().order_by('-created_at')[:10]  # Recent 10
    
    context = {
        'purchase_order': po,
        'billing_runs': billing_runs,
        'total_billed': billing_runs.aggregate(total=Sum('amount'))['total'] or 0,
    }
    return render(request, 'purchase_orders/detail.html', context)

@login_required
def edit_purchase_order(request, pk):
    """Edit an existing purchase order with enhanced balance handling"""
    po = get_object_or_404(PurchaseOrder, pk=pk)
    
    if request.method == 'POST':
        # Use the specialized edit form
        form = PurchaseOrderEditForm(request.POST, instance=po)
        if form.is_valid():
            updated_po = form.save()
            
            # Update account status if account exists
            if updated_po.account:
                updated_po.account.update_status()
            
            messages.success(request, f'Purchase Order {updated_po.po_number} updated successfully!')
            return redirect('purchase_orders:list')
        else:
            # Add form errors to messages for better user feedback
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    else:
        # Use the specialized edit form for GET request
        form = PurchaseOrderEditForm(instance=po)
    
    context = {
        'form': form, 
        'purchase_order': po,
        'is_edit_mode': True  # Flag to help template distinguish edit vs create
    }
    return render(request, 'purchase_orders/edit.html', context)

@login_required
def delete_purchase_order(request, pk):
    """Delete a purchase order (with confirmation)"""
    po = get_object_or_404(PurchaseOrder, pk=pk)
    
    if request.method == 'POST':
        po.delete()
        messages.success(request, 'Purchase Order deleted successfully!')
        return redirect('purchase_orders:list')
    
    return render(request, 'purchase_orders/delete.html', {'purchase_order': po})

@login_required
def export_purchase_orders(request):
    """Export purchase orders to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="purchase_orders_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'PO Number', 'Customer', 'Account', 'Total Amount', 'Remaining Balance',
        'Utilization %', 'Valid From', 'Valid Until', 'Status', 'Created Date',
        'Created By', 'Days Until Expiry'
    ])
    
    pos = PurchaseOrder.objects.select_related('customer', 'account', 'created_by').all()
    
    for po in pos:
        writer.writerow([
            po.po_number,
            po.customer.name,
            po.account.name if po.account else '',
            po.total_amount,
            po.remaining_balance,
            f"{po.utilization_percentage:.1f}%",
            po.valid_from,
            po.valid_until,
            po.get_status_display(),
            po.created_at.strftime('%Y-%m-%d'),
            po.created_by.get_full_name() or po.created_by.username,
            po.days_until_expiry
        ])
    
    return response

# API endpoints for AJAX functionality

@login_required
def get_purchase_order_api(request, pk):
    """Get purchase order details via API"""
    try:
        po = get_object_or_404(PurchaseOrder, pk=pk)
        recent_billing = po.billingrun_set.order_by('-created_at')[:5]
        
        data = {
            'id': po.id,
            'po_number': po.po_number,
            'customer_name': po.customer.name,
            'account_name': po.account.name if po.account else None,
            'total_amount': str(po.total_amount),
            'remaining_balance': str(po.remaining_balance),
            'utilization_percentage': f"{po.utilization_percentage:.1f}",
            'valid_from': po.valid_from.strftime('%Y-%m-%d'),
            'valid_until': po.valid_until.strftime('%Y-%m-%d'),
            'status': po.get_status_display(),
            'days_until_expiry': po.days_until_expiry,
            'recent_billing_runs': [
                {
                    'run_id': br.run_id,
                    'amount': str(br.amount),
                    'billing_date': br.billing_date.strftime('%Y-%m-%d'),
                    'status': br.get_status_display()
                } for br in recent_billing
            ]
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def duplicate_purchase_order_api(request, pk):
    """Duplicate a purchase order via API"""
    try:
        original_po = get_object_or_404(PurchaseOrder, pk=pk)
        
        # Create duplicate with modified PO number
        new_po_number = f"{original_po.po_number}-COPY-{date.today().strftime('%m%d')}"
        
        # Ensure unique PO number
        counter = 1
        while PurchaseOrder.objects.filter(po_number=new_po_number).exists():
            new_po_number = f"{original_po.po_number}-COPY-{date.today().strftime('%m%d')}-{counter}"
            counter += 1
        
        new_po = PurchaseOrder.objects.create(
            po_number=new_po_number,
            customer=original_po.customer,
            account=original_po.account,
            total_amount=original_po.total_amount,
            remaining_balance=original_po.total_amount,  # Reset to full amount
            valid_from=date.today(),  # Start from today
            valid_until=date.today() + timedelta(days=365),  # Default 1 year
            created_by=request.user,
            status='draft'  # Start as draft
        )
        
        return JsonResponse({
            'success': True,
            'new_po_id': new_po.id,
            'new_po_number': new_po.po_number,
            'message': 'Purchase order duplicated successfully!'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["DELETE"])
def delete_purchase_order_api(request, pk):
    """Delete a purchase order via API"""
    try:
        po = get_object_or_404(PurchaseOrder, pk=pk)
        
        # Check if PO has associated billing runs
        billing_runs_count = po.billingrun_set.count()
        if billing_runs_count > 0:
            return JsonResponse({
                'success': False,
                'error': f'Cannot delete PO with {billing_runs_count} associated billing runs. Please delete billing runs first.'
            }, status=400)
        
        po_number = po.po_number
        po.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Purchase order {po_number} deleted successfully!'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def get_customer_accounts_for_po(request, customer_id):
    """Get accounts for a customer (for PO creation)"""
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        accounts = Account.objects.filter(customer=customer, is_active=True)
        
        accounts_data = [
            {
                'id': account.id,
                'account_id': account.account_id or f'ACC-{account.id}',
                'name': account.name,
                'currency': getattr(account, 'currency', 'USD'),
                'display_name': f"{account.account_id or f'ACC-{account.id}'} - {account.name}"
            } for account in accounts
        ]
        
        return JsonResponse({
            'success': True,
            'accounts': accounts_data,
            'customer_name': customer.name,
            'customer_code': customer.name[:3].upper() 
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def get_notifications_api(request):
    """Get unread notifications for current user"""
    try:
        # Broaden the filter to show notifications for all POs the user can access
        notifications = POBalanceNotification.objects.filter(
            is_read=False
        ).select_related('purchase_order', 'purchase_order__customer').order_by('-created_at')[:10]
        
        notification_data = []
        for notification in notifications:
            notification_data.append({
                'id': notification.id,
                'message': notification.message,
                'priority_class': notification.priority_class,
                'po_number': notification.purchase_order.po_number,
                'customer_name': notification.purchase_order.customer.name,
                'utilization_percentage': f"{notification.utilization_percentage:.1f}",
                'remaining_balance': str(notification.remaining_balance),
                'threshold_percentage': notification.threshold_percentage,
                'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M'),
                'po_detail_url': f'/purchase-orders/{notification.purchase_order.id}/',
                'time_ago': get_time_ago(notification.created_at)
            })
        
        return JsonResponse({
            'success': True,
            'notifications': notification_data,
            'unread_count': notifications.count()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def mark_notification_read_api(request, notification_id):
    """Mark a notification as read"""
    try:
        notification = get_object_or_404(
            POBalanceNotification,
            id=notification_id,
            purchase_order__created_by=request.user  # Security check
        )
        notification.is_read = True
        notification.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read_api(request):
    """Mark all notifications as read for current user"""
    try:
        count = POBalanceNotification.objects.filter(
            is_read=False,
            purchase_order__created_by=request.user
        ).update(is_read=True)
        
        return JsonResponse({
            'success': True,
            'message': f'{count} notifications marked as read'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

def get_time_ago(created_at):
    """Helper function to get human readable time ago"""
    from django.utils import timezone
    from datetime import timedelta
    
    now = timezone.now()
    diff = now - created_at
    
    if diff < timedelta(minutes=1):
        return 'Just now'
    elif diff < timedelta(hours=1):
        minutes = diff.seconds // 60
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    elif diff < timedelta(days=1):
        hours = diff.seconds // 3600
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    elif diff < timedelta(days=7):
        return f'{diff.days} day{"s" if diff.days != 1 else ""} ago'
    else:
        return created_at.strftime('%b %d, %Y')


@login_required
def test_notification_system(request):
    """Test endpoint to trigger notifications manually"""
    from django.utils import timezone
    
    # Create a test notification
    if PurchaseOrder.objects.exists():
        po = PurchaseOrder.objects.first()
        notification = POBalanceNotification.objects.create(
            purchase_order=po,
            threshold_percentage=75,
            utilization_percentage=80.5,
            remaining_balance=po.remaining_balance,
            created_at=timezone.now(),
            is_read=False
        )
        
        messages.success(request, f"Test notification created for {po.po_number}")
    
    return redirect('purchase_orders:list')


@login_required
@require_POST
@csrf_protect
def clear_pdf_data(request):
    """Clear PDF-related session data"""
    session_keys = ['current_pdf_upload_id', 'extracted_pdf_data']
    cleared = False
    for key in session_keys:
        if key in request.session:
            del request.session[key]
            cleared = True
    if cleared:
        request.session.modified = True
        logger.debug("Cleared PDF session data")
    return JsonResponse({'success': True})


@login_required
def debug_pdf_extraction(request):
    """Temporary debug view to check session data"""
    pdf_data = request.session.get('extracted_pdf_data')
    
    context = {
        'has_session_data': pdf_data is not None,
        'pdf_data': pdf_data,
        'session_keys': list(request.session.keys()),
    }
    
    return render(request, 'purchase_orders/debug_pdf.html', context)