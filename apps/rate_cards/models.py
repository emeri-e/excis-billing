from decimal import Decimal
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
        ("Active", "Active"),
        ("Pending", "Pending"),
        ("Inactive", "Inactive"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="ratecards"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_ratecards",
    )
    region = models.CharField(max_length=64, blank=True)
    country = models.CharField(max_length=64, blank=True)
    supplier = models.CharField(max_length=128, blank=True)
    currency = models.CharField(max_length=8, default="USD")
    entity = models.CharField(max_length=128, blank=True)
    payment_terms = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # optional: free-form JSON field for flexible columns (Postgres JSONField recommended)
    # from django.contrib.postgres.fields import JSONField  # if using Postgres
    # meta = JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.customer} ({self.region} / {self.country})"


class ServiceRate(models.Model):
    RATE_TYPE_CHOICES = [
        ("hourly", "hourly"),
        ("day", "day"),
        ("monthly", "monthly"),
        ("fixed", "fixed"),
    ]
    rate_card = models.ForeignKey(
        RateCard, on_delete=models.CASCADE, related_name="service_rates"
    )
    category = models.CharField(
        max_length=64
    )  # e.g., 'Dispatch', 'FTE', 'Scheduled Visit'
    region = models.CharField(max_length=128, blank=True)
    rate_type = models.CharField(max_length=32, default="hourly")
    rate_value = models.DecimalField(max_digits=12, decimal_places=2)
    after_hours_multiplier = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )
    weekend_multiplier = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )
    travel_charge = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal(0)
    )
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.rate_card} — {self.category} ({self.region})"


class DedicatedServices(models.Model):

    rate_card = models.ForeignKey(
        RateCard, on_delete=models.CASCADE, related_name="dedicated_services_rate"
    )
    band0_with = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    band0_without = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    band1_with = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    band1_without = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    band2_with = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    band2_without = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    band3_with = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    band3_without = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    band4_with = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    band4_without = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return "Dedicated Service for %s" % self.rate_card.customer.name

    def to_dict(self) -> dict[str, str | dict[str, Decimal | None]]:
        return {
            "id": self.pk,
            "customer": self.rate_card.customer.name,
            "region": self.rate_card.region,
            "country": self.rate_card.country,
            "supplier": self.rate_card.supplier,
            "currency": self.rate_card.currency,
            "entity": self.rate_card.entity,
            "payment": self.rate_card.payment_terms,
            "band1": {"with": self.band1_with, "without": self.band1_without},
            "band2": {"with": self.band2_with, "without": self.band2_without},
            "band3": {"with": self.band3_with, "without": self.band3_without},
            "band4": {"with": self.band4_with, "without": self.band4_without},
            "status": self.rate_card.status,
        }


class ScheduledServices(models.Model):

    rate_card = models.ForeignKey(
        RateCard, on_delete=models.CASCADE, related_name="schedule_services_rate"
    )
    full_day_band0 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    full_day_band1 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    full_day_band2 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    half_day_band0 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    half_day_band1 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    half_day_band2 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return "Schedule service for %s" % self.rate_card.customer.name

    def to_dict(self) -> dict[str, str | dict[str, Decimal | None]]:
        return {
            "id": self.pk,
            "customer": self.rate_card.customer.name,
            "region": self.rate_card.region,
            "country": self.rate_card.country,
            "supplier": self.rate_card.supplier,
            "currency": self.rate_card.currency,
            "entity": self.rate_card.entity,
            "payment": self.rate_card.payment_terms,
            "full_day": {
                "band0": self.full_day_band0,
                "band1": self.full_day_band1,
                "band2": self.full_day_band2,
            },
            "half_day": {
                "band0": self.half_day_band0,
                "band1": self.half_day_band1,
                "band2": self.half_day_band2,
            },
            "status": self.rate_card.status,
        }


class DispatchServices(models.Model):

    rate_card = models.ForeignKey(
        RateCard, on_delete=models.CASCADE, related_name="dispatch_service_rate"
    )

    incident_4_hour = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    incident_sbn = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    incident_nbd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    incident_2bd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    incident_3bd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    incident_additional_hour = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    imac_2bd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    imac_3bd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    imac_4bd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    def __str__(self) -> str:
        return "Dispatch Service for %s" % self.rate_card.customer.name

    def to_dict(self) -> dict[str, str | dict[str, Decimal | None]]:
        return {
            "id": self.pk,
            "customer": self.rate_card.customer.name,
            "region": self.rate_card.region,
            "country": self.rate_card.country,
            "supplier": self.rate_card.supplier,
            "currency": self.rate_card.currency,
            "entity": self.rate_card.entity,
            "payment": self.rate_card.payment_terms,
            "Dispatch Ticket (incident)": {
                "4 hour": self.incident_4_hour,
                "SBN": self.incident_sbn,
                "NBD": self.incident_nbd,
                "2 BD": self.incident_2bd,
                "3 BD": self.incident_3bd,
                "additional hour": self.incident_additional_hour,
            },
            "Dispatch Ticket (IMAC)": {
                "2 BD": self.imac_2bd,
                "3 BD": self.imac_3bd,
                "4 BD": self.imac_4bd,
            },
            "status": self.rate_card.status,
        }


class Project(models.Model):

    rate_card = models.ForeignKey(
        RateCard, on_delete=models.CASCADE, related_name="project_rate"
    )

    short_term_band0 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    short_term_band1 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    short_term_band2 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    short_term_band3 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    short_term_band4 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    long_term_band0 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    long_term_band1 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    long_term_band2 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    long_term_band3 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    long_term_band4 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    def __str__(self) -> str:
        return "Project for %s" % self.rate_card.customer.name

    def to_dict(self) -> dict[str, str | dict[str, Decimal | None]]:
        return {
            "id": self.pk,
            "customer": self.rate_card.customer.name,
            "region": self.rate_card.region,
            "country": self.rate_card.country,
            "supplier": self.rate_card.supplier,
            "currency": self.rate_card.currency,
            "entity": self.rate_card.entity,
            "payment": self.rate_card.payment_terms,
            "Short Term (Up to 3 Month)": {
                "band0": self.short_term_band0,
                "band1": self.short_term_band1,
                "band2": self.short_term_band2,
                "band3": self.short_term_band3,
                "band4": self.short_term_band4,
            },
            "Long Term (More than 3 Months)": {
                "band0": self.long_term_band0,
                "band1": self.long_term_band1,
                "band2": self.long_term_band2,
                "band3": self.long_term_band3,
                "band4": self.long_term_band4,
            },
            "status": self.rate_card.status,
        }
