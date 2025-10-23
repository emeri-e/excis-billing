import json
import csv
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from datetime import date, timedelta
import logging

from .models import PurchaseOrder, POBalanceNotification, PurchaseOrderCSV
from apps.customers.models import Customer, Account

logger = logging.getLogger(__name__)

@login_required
def purchase_order_list(request):
    """Enhanced purchase order list with KPIs"""
    pos = PurchaseOrder.objects.select_related('customer', 'account').order_by('-created_at')
    
    # Filters
    status_filter = request.GET.get('status')
    customer_filter = request.GET.get('customer')
    currency_filter = request.GET.get('currency')
    search_query = request.GET.get('search')
    
    if status_filter:
        pos = pos.filter(status=status_filter)
    if customer_filter:
        pos = pos.filter(customer_id=customer_filter)
    if currency_filter:
        pos = pos.filter(currency=currency_filter)
    if search_query:
        pos = pos.filter(Q(po_number__icontains=search_query))
    
    # KPIs
    all_pos = PurchaseOrder.objects.all()
    today = date.today()
    
    kpis = {
        'active_pos': all_pos.filter(status='active').count(),
        'total_value': all_pos.filter(status__in=['active', 'expiring_soon']).aggregate(
            total=Sum('total_amount'))['total'] or 0,
        'low_balance_pos': all_pos.filter(status='low_balance').count(),
        'expiring_soon': all_pos.filter(status='expiring_soon').count(),
    }
    
    # Unread notifications
    unread_notifications = POBalanceNotification.objects.filter(
        is_read=False
    ).count()
    
    total_count = pos.count()
    
    # Pagination
    paginator = Paginator(pos, 15)
    page_number = request.GET.get('page')
    pos = paginator.get_page(page_number)
    
    # Filter options
    customers = Customer.objects.filter(is_active=True).order_by('name')
    currencies = PurchaseOrder.objects.values_list('currency', flat=True).distinct().order_by('currency')
    print("Distinct currencies:", list(currencies))
    
    context = {
        'purchase_orders': pos,
        'kpis': kpis,
        'customers': customers,
        'currencies': currencies,
        'status_filter': status_filter,
        'customer_filter': customer_filter,
        'currency_filter': currency_filter,
        'search_query': search_query,
        'status_choices': PurchaseOrder.STATUS_CHOICES,
        'total_count': total_count,
        'unread_notifications': unread_notifications,
    }
    return render(request, 'purchase_orders/list.html', context)


@login_required
@require_POST
def upload_csv(request):
    """Handle CSV upload and parse data"""
    try:
        if 'csv_file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No file uploaded'}, status=400)
        
        csv_file = request.FILES['csv_file']
        
        # Validate file
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({'success': False, 'error': 'Only CSV files allowed'}, status=400)
        
        if csv_file.size > 50 * 1024 * 1024:  # 5MB limit
            return JsonResponse({'success': False, 'error': 'File too large (max 5MB)'}, status=400)
        
        # Create CSV upload record
        csv_upload = PurchaseOrderCSV(
            csv_file=csv_file,
            original_filename=csv_file.name,
            uploaded_by=request.user
        )
        csv_upload.save()
        
        # Extract data
        extracted_data = csv_upload.extract_csv_data()
        
        if not extracted_data or not csv_upload.extraction_success:
            return JsonResponse({
                'success': False,
                'error': f'CSV extraction failed: {csv_upload.extraction_errors}'
            }, status=400)
        
        # Try to match customer
        matched_customer = None
        customer_name = extracted_data.get('customer_name', '')
        
        if customer_name:
            # Try exact match
            try:
                matched_customer = Customer.objects.get(
                    code__iexact=customer_name,
                    is_active=True
                )
            except Customer.DoesNotExist:
                # Try partial match
                customers = Customer.objects.filter(
                    code__icontains=customer_name[:20],
                    is_active=True
                )
                if customers.count() == 1:
                    matched_customer = customers.first()
        
        if matched_customer:
            extracted_data['matched_customer_id'] = matched_customer.id
            extracted_data['matched_customer_name'] = matched_customer.name
        
        # Try to match account
        matched_account = None
        account_name = extracted_data.get('account_name', '').strip()
        
        if matched_customer and account_name:
            try:
                matched_account = Account.objects.get(
                    customer=matched_customer,
                    code__iexact=account_name,
                    is_active=True
                )
                extracted_data['matched_account_id'] = matched_account.id
            except Account.DoesNotExist:
                pass
        
        # Store in session
        request.session['csv_upload_id'] = csv_upload.id
        request.session['extracted_csv_data'] = extracted_data
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'data': extracted_data,
            'message': 'CSV parsed successfully'
        })
        
    except Exception as e:
        logger.error(f"CSV upload error: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def bulk_create_pos_from_csv(request):
    """Create multiple POs from uploaded CSV data with optional account filtering"""
    try:
        data = json.loads(request.body)
        
        # Get CSV data from session
        extracted_data = request.session.get('extracted_csv_data')
        if not extracted_data:
            return JsonResponse({
                'success': False,
                'error': 'No CSV data found. Please upload CSV first.'
            }, status=400)
        
        customer_name = extracted_data.get('customer_name', '')
        po_records = extracted_data.get('po_records', [])
        
        # Apply account filter if provided
        account_filter = data.get('account_filter')
        if account_filter:
            po_records = [r for r in po_records if r.get('account_name') == account_filter]
            logger.info(f"Filtered to {len(po_records)} records for account: {account_filter}")
        
        # Helper function to convert date strings to date objects
        def ensure_date(value):
            """Convert string or date to date object"""
            if not value:
                return date.today()
            if isinstance(value, date):
                return value
            if isinstance(value, str):
                try:
                    from datetime import datetime
                    # Try parsing common formats
                    for fmt in ['%Y-%m-%d', '%d-%b-%y', '%d-%b-%Y', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y']:
                        try:
                            return datetime.strptime(value.strip(), fmt).date()
                        except:
                            continue
                    # If all parsing fails, return today
                    return date.today()
                except:
                    return date.today()
            return date.today()
        
        # Get or create customer
        customer_id = data.get('customer_id')
        if customer_id:
            customer = get_object_or_404(Customer, id=customer_id, is_active=True)
        elif customer_name:
            # Create new customer
            customer_code = customer_name[:3].upper()
            counter = 1
            original_code = customer_code
            while Customer.objects.filter(code=customer_code).exists():
                customer_code = f"{original_code}{counter}"
                counter += 1
            
            customer = Customer.objects.create(
                name=customer_name,
                code=customer_code,
                email=f"{customer_code.lower()}@example.com",
                created_by=request.user
            )
        else:
            return JsonResponse({
                'success': False,
                'error': 'Customer is required'
            }, status=400)
        
        # Track creation results
        created_pos = []
        created_accounts = []
        errors = []
        
        # Create POs from records
        for idx, record in enumerate(po_records):
            try:
                account_name = record.get('account_name', '').strip()
                account = None
                
                # Get or create account
                if account_name:
                    try:
                        account = Account.objects.get(
                            customer=customer,
                            name__iexact=account_name,
                            is_active=True
                        )
                    except Account.DoesNotExist:
                        # Create new account
                        from apps.customers.models import Currency, BillingCycle
                        
                        currency_code = record.get('currency', 'USD')
                        currency, _ = Currency.objects.get_or_create(
                            code=currency_code,
                            defaults={'name': currency_code}
                        )
                        
                        billing_cycle, _ = BillingCycle.objects.get_or_create(
                            name='Monthly',
                            defaults={'cycle_type': 'monthly', 'customer': customer}
                        )
                        
                        account_id_str = f"{customer.code}-{account_name[:3].upper()}-{idx+1:03d}"
                        
                        account = Account.objects.create(
                            customer=customer,
                            name=account_name,
                            account_id=account_id_str,
                            region='Global',
                            billing_cycle=billing_cycle,
                            currency=currency,
                            created_by=request.user
                        )
                        created_accounts.append(account.name)
                
                # Generate PO number
                po_number = record.get('po_number', '')
                if not po_number:
                    po_number = f"PO-{customer.code}-{date.today().year}-{idx+1:04d}"
                
                # Create PO
                po = PurchaseOrder.objects.create(
                    po_number=po_number,
                    customer=customer,
                    account=account,
                    currency=record.get('currency', 'USD'),
                    total_amount=max(0, float(record.get('total_amount', 0))),
                    spent_amount=max(0, float(record.get('spent_amount', 0))),
                    valid_from=ensure_date(record.get('valid_from')),
                    valid_until=ensure_date(record.get('valid_until')),
                    project=account_name,  # Store account name in project field
                    sdm=record.get('sdm', ''),
                    bill_to=record.get('bill_to', ''),
                    billing_address=record.get('billing_address', ''),
                    about=record.get('about', ''),
                    work_done=record.get('work_done', ''),
                    comment=record.get('comment', ''),
                    expiration_days=record.get('expiration_days'),
                    payment_terms=record.get('payment_terms', ''),
                    client_year=record.get('client_year', ''),
                    created_by=request.user,
                    status='active' if record.get('po_status', '').upper() == 'ACTIVE' else 'inactive'
                )
                
                created_pos.append(po.po_number)
            
            except Exception as e:
                errors.append(f"Row {idx + 1}: {str(e)}")
                continue
        
        # Link CSV upload to first PO
        csv_upload_id = request.session.get('csv_upload_id')
        if csv_upload_id and created_pos:
            try:
                csv_upload = PurchaseOrderCSV.objects.get(id=csv_upload_id)
                first_po = PurchaseOrder.objects.get(po_number=created_pos[0])
                csv_upload.purchase_order = first_po
                csv_upload.save()
            except:
                pass
        
        # Clear session
        request.session.pop('csv_upload_id', None)
        request.session.pop('extracted_csv_data', None)
        request.session.pop('response_data', None)
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'created_pos': len(created_pos),
            'created_accounts': len(created_accounts),
            'errors': len(errors),
            'po_numbers': created_pos,
            'account_names': created_accounts,
            'error_details': errors if errors else None,
            'message': f'Created {len(created_pos)} POs successfully' + 
                      (f' with {len(errors)} errors' if errors else '')
        })
        
    except Exception as e:
        logger.error(f"Bulk PO creation error: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def create_purchase_order_api(request):
    """Create PO via API (AJAX)"""
    try:
        data = json.loads(request.body)
        
        # Get or create customer
        customer_id = data.get('customer_id')
        customer_name = data.get('customer_name', '')
        
        if customer_id:
            customer = get_object_or_404(Customer, id=customer_id, is_active=True)
        elif customer_name:
            # Create new customer
            customer_code = customer_name[:3].upper()
            counter = 1
            original_code = customer_code
            while Customer.objects.filter(code=customer_code).exists():
                customer_code = f"{original_code}{counter}"
                counter += 1
            
            customer = Customer.objects.create(
                name=customer_name,
                code=customer_code,
                email=f"{customer_code.lower()}@example.com",
                created_by=request.user
            )
            messages.success(request, f"Created new customer: {customer.name}")
        else:
            return JsonResponse({'success': False, 'error': 'Customer is required'}, status=400)
        
        # Get or create account
        account = None
        account_id = data.get('account_id')
        account_name = data.get('account_name', '').strip()
        
        if account_id:
            account = get_object_or_404(Account, id=account_id, customer=customer, is_active=True)
        elif account_name:
            # Create new account
            from apps.customers.models import Currency, BillingCycle
            
            currency, _ = Currency.objects.get_or_create(
                code=data.get('currency', 'USD'),
                defaults={'name': data.get('currency', 'USD')}
            )
            
            billing_cycle, _ = BillingCycle.objects.get_or_create(
                name='Monthly',
                defaults={'cycle_type': 'monthly', 'customer': customer}
            )
            
            account_id_str = f"{customer.code}-{account_name[:3].upper()}-001"
            counter = 1
            original_id = account_id_str
            while Account.objects.filter(account_id=account_id_str).exists():
                account_id_str = f"{original_id[:-3]}{counter:03d}"
                counter += 1
            
            account = Account.objects.create(
                customer=customer,
                name=account_name,
                account_id=account_id_str,
                region=data.get('region', 'Global'),
                billing_cycle=billing_cycle,
                currency=currency,
                created_by=request.user
            )
            messages.success(request, f"Created new account: {account.name}")
        
        # Parse dates from string to date objects
        from datetime import datetime
        
        valid_from_str = data.get('valid_from')
        valid_until_str = data.get('valid_until')
        
        try:
            valid_from = datetime.strptime(valid_from_str, '%Y-%m-%d').date() if valid_from_str else date.today()
        except (ValueError, TypeError):
            valid_from = date.today()
        
        try:
            valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d').date() if valid_until_str else date.today()
        except (ValueError, TypeError):
            valid_until = date.today()
        
        # Create PO
        po = PurchaseOrder.objects.create(
            po_number=data.get('po_number', ''),
            customer=customer,
            account=account,
            currency=data.get('currency', 'USD'),
            total_amount=data.get('total_amount', 0),
            spent_amount=data.get('spent_amount', 0),
            valid_from=valid_from,
            valid_until=valid_until,
            project=data.get('project', ''),
            sdm=data.get('sdm', ''),
            bill_to=data.get('bill_to', ''),
            billing_address=data.get('billing_address', ''),
            about=data.get('about', ''),
            work_done=data.get('work_done', ''),
            comment=data.get('comment', ''),
            expiration_days=data.get('expiration_days'),
            payment_terms=data.get('payment_terms', ''),
            client_year=data.get('client_year', ''),
            created_by=request.user
        )
        
        # Link CSV if exists
        csv_upload_id = request.session.get('csv_upload_id')
        if csv_upload_id:
            try:
                csv_upload = PurchaseOrderCSV.objects.get(id=csv_upload_id)
                csv_upload.purchase_order = po
                csv_upload.save()
            except PurchaseOrderCSV.DoesNotExist:
                pass
        
        # Clear session
        request.session.pop('csv_upload_id', None)
        request.session.pop('extracted_csv_data', None)
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'po_id': po.id,
            'po_number': po.po_number,
            'message': f'PO {po.po_number} created successfully'
        })
        
    except Exception as e:
        logger.error(f"Create PO error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def update_purchase_order_api(request, pk):
    """Update PO via API (AJAX)"""
    try:
        po = get_object_or_404(PurchaseOrder, id=pk)
        data = json.loads(request.body)
        
        # Parse dates if provided
        from datetime import datetime
        
        valid_from_str = data.get('valid_from')
        valid_until_str = data.get('valid_until')
        
        if valid_from_str:
            try:
                po.valid_from = datetime.strptime(valid_from_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        
        if valid_until_str:
            try:
                po.valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        
        # Update other fields
        po.currency = data.get('currency', po.currency)
        po.total_amount = data.get('total_amount', po.total_amount)
        po.spent_amount = data.get('spent_amount', po.spent_amount)
        po.project = data.get('project', po.project)
        po.sdm = data.get('sdm', po.sdm)
        po.bill_to = data.get('bill_to', po.bill_to)
        po.billing_address = data.get('billing_address', po.billing_address)
        po.about = data.get('about', po.about)
        po.work_done = data.get('work_done', po.work_done)
        po.comment = data.get('comment', po.comment)
        po.expiration_days = data.get('expiration_days', po.expiration_days)
        po.payment_terms = data.get('payment_terms', po.payment_terms)
        po.client_year = data.get('client_year', po.client_year)
        
        po.save()
        
        return JsonResponse({
            'success': True,
            'message': f'PO {po.po_number} updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Update PO error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def get_purchase_order_api(request, pk):
    """Get PO details via API"""
    try:
        po = get_object_or_404(PurchaseOrder, id=pk)
        
        data = {
            'id': po.id,
            'po_number': po.po_number,
            'customer_id': po.customer.id,
            'customer_name': po.customer.name,
            'account_id': po.account.id if po.account else None,
            'account_name': po.account.name if po.account else '',
            'currency': po.currency,
            'total_amount': str(po.total_amount),
            'spent_amount': str(po.spent_amount),
            'remaining_balance': str(po.remaining_balance),
            'valid_from': po.valid_from.strftime('%Y-%m-%d'),
            'valid_until': po.valid_until.strftime('%Y-%m-%d'),
            'project': po.project or '',
            'sdm': po.sdm or '',
            'bill_to': po.bill_to or '',
            'billing_address': po.billing_address or '',
            'about': po.about or '',
            'work_done': po.work_done or '',
            'comment': po.comment or '',
            'expiration_days': po.expiration_days,
            'payment_terms': po.payment_terms or '',
            'client_year': po.client_year or '',
            'status': po.get_status_display(),
            'utilization_percentage': f"{po.utilization_percentage:.1f}",
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        logger.error(f"Get PO error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_purchase_order_api(request, pk):
    """Delete PO via API"""
    try:
        po = get_object_or_404(PurchaseOrder, id=pk)
        po_number = po.po_number
        po.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'PO {po_number} deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Delete PO error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def export_purchase_orders(request):
    """Export POs to CSV - all or selected"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="po_export.csv"'
   
    writer = csv.writer(response)
    writer.writerow([
        'UID', 'PO Number', 'Customer', 'Account', 'Currency', 'Total', 'Spent',
        'Remaining', 'Valid From', 'Valid Until', 'Status', 'Project', 'SDM',
        'Bill To', 'Billing Address', 'About', 'Work Done', 'Comment',
        'Expiration Days', 'Payment Terms', 'Client Year'
    ])
   
    # Check if specific IDs are requested
    selected_ids = request.GET.get('ids', '')
    
    if selected_ids:
        # Export only selected rows
        id_list = [id.strip() for id in selected_ids.split(',') if id.strip()]
        pos = PurchaseOrder.objects.filter(id__in=id_list).select_related('customer', 'account')
    else:
        # Export all (you can also apply filters here if needed)
        pos = PurchaseOrder.objects.select_related('customer', 'account').all()
        
        # Optional: Apply the same filters from the list view
        customer_filter = request.GET.get('customer')
        status_filter = request.GET.get('status')
        currency_filter = request.GET.get('currency')
        search_query = request.GET.get('search')
        
        if customer_filter:
            pos = pos.filter(customer_id=customer_filter)
        if status_filter:
            pos = pos.filter(status=status_filter)
        if currency_filter:
            pos = pos.filter(currency=currency_filter)
        if search_query:
            pos = pos.filter(po_number__icontains=search_query)
   
    for po in pos:
        writer.writerow([
            po.id,
            po.po_number,
            po.customer.name,
            po.account.name if po.account else '',
            po.currency,
            po.total_amount,
            po.spent_amount,
            po.remaining_balance,
            po.valid_from,
            po.valid_until,
            po.get_status_display(),
            po.project or '',
            po.sdm or '',
            po.bill_to or '',
            po.billing_address or '',
            po.about or '',
            po.work_done or '',
            po.comment or '',
            po.expiration_days or '',
            po.payment_terms or '',
            po.client_year or '',
        ])
   
    return response


@login_required
def get_notifications_api(request):
    """Get unread notifications"""
    try:
        notifications = POBalanceNotification.objects.filter(
            is_read=False
        ).select_related('purchase_order', 'purchase_order__customer').order_by('-created_at')[:10]
        
        notification_data = []
        for notification in notifications:
            try:
                notification_data.append({
                    'id': notification.id,
                    'message': notification.message,
                    'priority_class': notification.priority_class,
                    'po_number': notification.purchase_order.po_number,
                    'customer_name': notification.purchase_order.customer.name,
                    'utilization_percentage': f"{float(notification.utilization_percentage):.1f}",
                    'remaining_balance': str(float(notification.remaining_balance)),
                    'threshold_percentage': notification.threshold_percentage,
                    'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M'),
                    'po_id': notification.purchase_order.id,
                })
            except (ValueError, TypeError, Exception) as e:
                # Skip corrupt notifications and log the error
                logger.warning(f"Skipping corrupt notification {notification.id}: {e}")
                continue
        
        return JsonResponse({
            'success': True,
            'notifications': notification_data,
            'unread_count': len(notification_data)
        })
        
    except Exception as e:
        logger.error(f"Get notifications error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def mark_notification_read_api(request, notification_id):
    """Mark notification as read"""
    try:
        notification = get_object_or_404(POBalanceNotification, id=notification_id)
        notification.is_read = True
        notification.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def mark_all_notifications_read_api(request):
    """Mark all notifications as read"""
    try:
        count = POBalanceNotification.objects.filter(
            is_read=False
        ).update(is_read=True)
        
        return JsonResponse({
            'success': True,
            'message': f'{count} notifications marked as read'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)