from django.db import models
from django.contrib.auth.models import User
from apps.customers.models import Customer

class RateCard(models.Model):
    name = models.CharField(max_length=200)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)
    rate_per_unit = models.DecimalField(max_digits=10, decimal_places=4)
    unit_type = models.CharField(max_length=50, default='hour')
    valid_from = models.DateField()
    valid_until = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.customer.name}"