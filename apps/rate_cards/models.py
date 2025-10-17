from django.db import models
from django.contrib.auth.models import User
from apps.customers.models import Customer

# class RateCard(models.Model):
#     name = models.CharField(max_length=200)
#     customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
#     description = models.TextField(blank=True, null=True)
#     rate_per_unit = models.DecimalField(max_digits=10, decimal_places=4)
#     unit_type = models.CharField(max_length=50, default='hour')
#     valid_from = models.DateField()
#     valid_until = models.DateField()
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
#     class Meta:
#         ordering = ['-created_at']

#     def __str__(self):
#         return f"{self.name} - {self.customer.name}"
from django.conf import settings

class RateCard(models.Model):
    STATUS_CHOICES = [
        ('Active','Active'),
        ('Pending','Pending'),
        ('Inactive','Inactive'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='ratecards')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_ratecards')
    region = models.CharField(max_length=64, blank=True)
    country = models.CharField(max_length=64, blank=True)
    supplier = models.CharField(max_length=128, blank=True)
    currency = models.CharField(max_length=8, default='USD')
    entity = models.CharField(max_length=128, blank=True)
    payment_terms = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # optional: free-form JSON field for flexible columns (Postgres JSONField recommended)
    # from django.contrib.postgres.fields import JSONField  # if using Postgres
    # meta = JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.customer} ({self.region} / {self.country})"


class ServiceRate(models.Model):
    RATE_TYPE_CHOICES = [
        ('hourly','hourly'),
        ('day','day'),
        ('monthly','monthly'),
        ('fixed','fixed'),
    ]
    rate_card = models.ForeignKey(RateCard, on_delete=models.CASCADE, related_name='service_rates')
    category = models.CharField(max_length=64)  # e.g., 'Dispatch', 'FTE', 'Scheduled Visit'
    region = models.CharField(max_length=128, blank=True)
    rate_type = models.CharField(max_length=32, default='hourly')
    rate_value = models.DecimalField(max_digits=12, decimal_places=2)
    after_hours_multiplier = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    weekend_multiplier = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    travel_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.rate_card} — {self.category} ({self.region})"
