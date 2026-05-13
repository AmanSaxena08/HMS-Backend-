# patients/migrations/0022_billing_onetoone_task_admission.py
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0021_add_indexes'),
        ('tasks', '0001_initial'),  # Adjust this to your latest tasks migration
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

        # Step 2: Convert ForeignKey to OneToOneField on Billing
        migrations.AlterField(
            model_name='billing',
            name='admission',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='billing',
                to='patients.admission',
            ),
        ),

        # Step 3: Add admission FK to Task (initially allow null for existing tasks)
        migrations.AddField(
            model_name='task',
            name='admission',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tasks',
                to='patients.admission',
            ),
        ),

        # Step 4: Populate Task.admission with preferred admission for each patient
        migrations.RunSQL(
            sql="""
            UPDATE tasks_task 
            SET admission_id = (
                SELECT id FROM patients_admission 
                WHERE patient_id = tasks_task.patient_id 
                ORDER BY admNo DESC LIMIT 1
            )
            WHERE patient_id IS NOT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # Step 5: Add unique constraint on ServiceMaster (description + pricing_type)
        migrations.AlterUniqueTogether(
            name='servicemaster',
            unique_together={('description', 'pricing_type')},
        ),

        # Step 6: Add indexes for frequently joined fields
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['patient', 'assigned_to'], name='task_patient_assignee_idx'),
        ),
        migrations.AddIndex(
            model_name='billing',
            index=models.Index(fields=['admission', 'bill_type'], name='billing_admission_type_idx'),
        ),
    ]