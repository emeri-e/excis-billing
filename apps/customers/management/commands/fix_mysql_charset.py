from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fix MySQL charset to utf8mb4 for all tables'

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            # Get all tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            for (table_name,) in tables:
                try:
                    self.stdout.write(f"Converting {table_name}...")
                    cursor.execute(
                        f"ALTER TABLE {table_name} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                    self.stdout.write(self.style.SUCCESS(f"✓ {table_name}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"✗ {table_name}: {e}"))
        
        self.stdout.write(self.style.SUCCESS('\n✓ All tables converted to utf8mb4'))