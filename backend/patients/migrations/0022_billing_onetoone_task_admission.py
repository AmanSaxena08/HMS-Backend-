# patients/migrations/0022_billing_onetoone_task_admission.py
#
# WHAT THIS MIGRATION DOES:
#   - Cleans duplicate billing rows (data fix)
#   - Converts Billing.admission from ForeignKey -> OneToOneField
#   - Adds billing_admission_type_idx index on Billing
#
# WHAT WAS REMOVED vs the original broken file:
#   Step 3 (AddField task.admission)             -> tasks/0002_task_admission_fk.py  [already exists]
#   Step 4 (RunSQL populate task.admission)      -> tasks/0002_task_admission_fk.py  [already exists]
#   Step 5 (AlterUniqueTogether servicemaster)   -> master/0002_servicemaster_unique_together.py [NEW]
#   Step 6a (AddIndex task_patient_assignee_idx) -> tasks/0002_task_admission_fk.py  [already exists]
#
# WHY:
#   (a) patients/0022 AND tasks/0002 were both trying to AddField task.admission
#       and both adding index 'task_patient_assignee_idx'. That's a duplicate
#       column + duplicate index crash.
#   (b) AlterUniqueTogether on 'servicemaster' in the patients app crashes with
#       KeyError because ServiceMaster was deleted from patients in migration 0018.
#       It now lives in master app.
#
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0021_add_indexes'),
        ('tasks', '0001_initial'),
    ]

    operations = [
        # Step 1: Delete duplicate billing rows (keep only the latest per admission)
        migrations.RunSQL(
            sql="""
            DELETE FROM patients_billing
            WHERE id NOT IN (
                SELECT MAX(id) FROM patients_billing GROUP BY admission_id
            )
            AND admission_id IS NOT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # Step 2: Convert Billing.admission ForeignKey -> OneToOneField
        migrations.AlterField(
            model_name='billing',
            name='admission',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='billing',
                to='patients.admission',
            ),
        ),

        # Step 6b: Index on Billing (belongs here, unchanged)
        migrations.AddIndex(
            model_name='billing',
            index=models.Index(
                fields=['admission', 'bill_type'],
                name='billing_admission_type_idx',
            ),
        ),
    ]