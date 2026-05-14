# tasks/migrations/0002_task_admission_fk.py
#
# USE THIS FILE AS-IS. No changes needed from what you already had.
# Listed here only so you have a confirmed-correct copy alongside the other fixes.
#
# Key decisions documented:
#   - on_delete=SET_NULL (not CASCADE): if an admission is deleted, the task
#     survives for audit trail. CASCADE would silently delete staff work history.
#   - RunSQL uses quoted "admNo" for PostgreSQL case-sensitivity.
#   - Index name 'task_patient_assignee_idx' defined only here (removed from 0022).
#
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0001_initial'),
        ('patients', '0022_billing_onetoone_task_admission'),
    ]

    operations = [
        # Add admission FK to Task (null for existing tasks)
        migrations.AddField(
            model_name='task',
            name='admission',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tasks',
                to='patients.admission',
            ),
        ),

        # Backfill: point each task to the patient's latest admission
        migrations.RunSQL(
            sql="""
            UPDATE tasks_task
            SET admission_id = (
                SELECT id FROM patients_admission
                WHERE patient_id = tasks_task.patient_id
                ORDER BY "admNo" DESC LIMIT 1
            )
            WHERE patient_id IS NOT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # Index on task patient + assignee
        migrations.AddIndex(
            model_name='task',
            index=models.Index(
                fields=['patient', 'assigned_to'],
                name='task_patient_assignee_idx',
            ),
        ),
    ]