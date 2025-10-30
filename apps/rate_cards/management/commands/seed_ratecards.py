from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

# Try a few import locations for Customer and rate models to be flexible across projects
try:
    from apps.customers.models import Customer
except Exception:
    try:
        from customers.models import Customer
    except Exception:
        Customer = None

RateCard = ServiceRate = DedicatedRate = ScheduledRate = DispatchRate = ProjectRate = None
model_imported = False
for mod_path in ("apps.rate_cards.models", "rate_cards.models", "rate_cards.models", "models"):
    if model_imported:
        break
    try:
        m = __import__(mod_path, fromlist=[
            "RateCard", "ServiceRate", "DedicatedRate", "ScheduledRate", "DispatchRate", "ProjectRate"
        ])
        RateCard = getattr(m, "RateCard", None)
        ServiceRate = getattr(m, "ServiceRate", None)
        DedicatedRate = getattr(m, "DedicatedRate", None)
        ScheduledRate = getattr(m, "ScheduledRate", None)
        DispatchRate = getattr(m, "DispatchRate", None)
        ProjectRate = getattr(m, "ProjectRate", None)
        if RateCard and ServiceRate:
            model_imported = True
    except Exception:
        continue

if not model_imported:
    raise ImportError(
        "Could not import RateCard/Rate models. Adjust the import path in the management command to match your app."
    )

User = get_user_model()


class Command(BaseCommand):
    help = "Seed database with sample customers, ratecards and several rate-like models."

    def handle(self, *args, **options):
        with transaction.atomic():
            # pick or create a user for created_by
            user = User.objects.filter(is_staff=True).first()
            if not user:
                user, _ = User.objects.get_or_create(username="seed_user", defaults={
                    "email": "seed_user@example.com",
                    "is_staff": True,
                })
                # set password if not set
                user.set_password("password")
                user.save()
                self.stdout.write(self.style.WARNING("Created seed_user with password 'password' — change immediately."))

            # create sample customers
            customers = [
                {"code": "HCL", "name": "HCL Technologies", "email": "finance@hcl.com"},
                {"code": "Cognizant", "name": "Cognizant", "email": "finance@cognizant.com"},
                {"code": "TCS", "name": "Tata Consultancy Services", "email": "finance@tcs.com"},
                {"code": "LEN-TH", "name": "Lenovo Thailand", "email": "finance.th@lenovo.com"},
                {"code": "ACME", "name": "Acme Corp", "email": "finance@acme.example"},
            ]

            created_customers = []
            for c in customers:
                if Customer:
                    cust, created = Customer.objects.get_or_create(code=c["code"], defaults={
                        "name": c["name"],
                        "email": c["email"],
                        "created_by": user,
                    })
                else:
                    # If Customer model not available, skip with a message
                    self.stdout.write(self.style.WARNING("Customer model not found; skipping Customer creation."))
                    cust = None
                    created = False
                created_customers.append(cust)
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Created Customer: {cust}"))
                elif cust:
                    self.stdout.write(self.style.NOTICE(f"Customer exists: {cust}"))

            # create 5 ratecards (one per customer)
            ratecards = []
            currencies = ["USD", "EUR", "USD", "THB", "GBP"]
            regions = ["EMEA", "APAC", "NA", "APAC", "EMEA"]
            countries = ["Germany", "India", "USA", "Thailand", "UK"]
            suppliers = ["Vendor A", "Vendor B", "Vendor C", "Vendor TH", "Vendor D"]
            payments = ["30 Days", "45 Days", "30 Days", "30 Days", "60 Days"]

            for i, cust in enumerate(created_customers):
                rc_defaults = {
                    "created_by": user,
                    "region": regions[i],
                    "country": countries[i],
                    "supplier": suppliers[i],
                    "currency": currencies[i],
                    "entity": f"E{i+1}",
                    "payment_terms": payments[i],
                    "status": "Active",
                }
                # Some Customer may be None if model missing; make RateCard only if RateCard model present
                if cust:
                    rc, created = RateCard.objects.get_or_create(customer=cust, defaults=rc_defaults)
                else:
                    # Create a RateCard without a Customer (fallback) if model allows null — but above model requires FK.
                    # So skip creation and continue.
                    self.stdout.write(self.style.WARNING("Skipping RateCard creation because Customer model missing."))
                    continue

                ratecards.append(rc)
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Created RateCard for {cust} (id={rc.id})"))
                else:
                    self.stdout.write(self.style.NOTICE(f"RateCard exists for {cust} (id={rc.id})"))

            # helper functions to populate different rate models
            def create_dedicated_rates(rc, base_with=26000, base_without=23000):
                bands = ['Band 0', 'Band 1', 'Band 2', 'Band 3', 'Band 4']
                objs = []
                for i, b in enumerate(bands):
                    with_val = Decimal(base_with + i * 2000)
                    without_val = Decimal(base_without + i * 1800)
                    objs.append(DedicatedRate.objects.create(
                        rate_card=rc, category=b, rate_type='With', rate_value=with_val, created_by=user
                    ))
                    objs.append(DedicatedRate.objects.create(
                        rate_card=rc, category=b, rate_type='Without', rate_value=without_val, created_by=user
                    ))
                return objs

            def create_scheduled_rates(rc, base=300):
                groups = [
                    ("Full Day Visit (8hrs)", ['Band 0', 'Band 1', 'Band 2']),
                    ("1/2 Day Visit (4hrs)", ['Band 0', 'Band 1', 'Band 2']),
                ]
                objs = []
                for g_idx, (title, bands) in enumerate(groups):
                    for i, b in enumerate(bands):
                        # multiply base for group to differentiate
                        val = Decimal(base + (g_idx * 50) + i * 20)
                        objs.append(ScheduledRate.objects.create(
                            rate_card=rc, category=title, rate_type=b, rate_value=val, created_by=user
                        ))
                return objs

            def create_dispatch_rates(rc, base_incident=100, base_imac=200):
                groups = [
                    ("Dispatch Ticket (Incident)", ['4 hour', 'SBD', 'NBD', '2 BD', '3 BD', 'Additional Hour']),
                    ("Dispatch Ticket (IMAC)", ['2 BD', '3 BD', '4 BD']),
                ]
                objs = []
                # Incident
                for i, b in enumerate(groups[0][1]):
                    val = Decimal(base_incident + i * 50)
                    objs.append(DispatchRate.objects.create(
                        rate_card=rc, category=groups[0][0], rate_type=b, rate_value=val, created_by=user
                    ))
                # IMAC
                for i, b in enumerate(groups[1][1]):
                    val = Decimal(base_imac + i * 75)
                    objs.append(DispatchRate.objects.create(
                        rate_card=rc, category=groups[1][0], rate_type=b, rate_value=val, created_by=user
                    ))
                return objs

            def create_project_rates(rc, base_short=5000, base_long=4500):
                # Short Term (Up to 3 months): Band 0..4
                # Long Term (more than 3 months): Band 0..4
                objs = []
                for i in range(5):
                    val = Decimal(base_short + i * 500)
                    objs.append(ProjectRate.objects.create(
                        rate_card=rc, category="Short Term (Up to 3 months)", rate_type=f"Band {i}", rate_value=val, created_by=user
                    ))
                for i in range(5):
                    val = Decimal(base_long + i * 450)
                    objs.append(ProjectRate.objects.create(
                        rate_card=rc, category="Long Term (more than 3 months)", rate_type=f"Band {i}", rate_value=val, created_by=user
                    ))
                return objs

            def create_service_rates(rc):
                # create a few generic service rates for demo
                objs = []
                objs.append(ServiceRate.objects.create(
                    rate_card=rc, category="Dispatch", region=rc.country or rc.region, rate_type="hourly", rate_value=Decimal(850), after_hours_multiplier=Decimal('1.5'), weekend_multiplier=Decimal('2.0'), travel_charge=Decimal('0.00'), created_by=user
                ))
                objs.append(ServiceRate.objects.create(
                    rate_card=rc, category="FTE", region=rc.country or rc.region, rate_type="monthly", rate_value=Decimal(60000), remarks="Level 2 engineer full-time placement", created_by=user
                ))
                objs.append(ServiceRate.objects.create(
                    rate_card=rc, category="Scheduled Visit", region=rc.country or rc.region, rate_type="day", rate_value=Decimal(3200), created_by=user
                ))
                return objs

            # populate each ratecard
            for idx, rc in enumerate(ratecards):
                # Keep a small variability between ratecards
                dw = create_dedicated_rates(rc, base_with=26000 + idx * 1000, base_without=23000 + idx * 800)
                sch = create_scheduled_rates(rc, base=300 + idx * 10)
                dis = create_dispatch_rates(rc, base_incident=100 + idx * 10, base_imac=200 + idx * 15)
                proj = create_project_rates(rc, base_short=5000 + idx * 200, base_long=4500 + idx * 150)
                svc = create_service_rates(rc)

                self.stdout.write(self.style.SUCCESS(
                    f"RateCard id={rc.id}: created {len(dw)} dedicated entries, {len(sch)} scheduled, {len(dis)} dispatch, {len(proj)} project, {len(svc)} service rates."
                ))

            self.stdout.write(self.style.SUCCESS("Seeding complete."))
