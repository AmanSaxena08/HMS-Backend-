# master/migrations/0002_servicemaster_unique_together.py
#
# Adds unique_together constraint on master.ServiceMaster (description, pricing_type).
#
# IMPORTANT: Before adding the constraint we must deduplicate existing rows.
# The DB already has duplicate (description, pricing_type) entries (e.g. "Super Speciality, CASH")
# imported from the Excel rate list. We keep the row with the highest id (latest import)
# and delete all earlier duplicates, then apply the unique index safely.
#
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0001_initial'),
        ('patients', '0022_billing_onetoone_task_admission'),
    ]

    operations = [
        # Step 1: Delete duplicate ServiceMaster rows.
        # Keep only the MAX(id) per (description, pricing_type) pair.
        # This is the same pattern used in patients/0022 for Billing deduplication.
        migrations.RunSQL(
            sql="""
            DELETE FROM master_servicemaster
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM master_servicemaster
                GROUP BY description, pricing_type
            );
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # Step 2: Now that duplicates are gone, apply the unique constraint safely.
        migrations.AlterUniqueTogether(
            name='servicemaster',
            unique_together={('description', 'pricing_type')},
        ),
    ]