from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('patients', '0020_labreport_admission_required'),
    ]
    operations = [
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['branch_location'], name='patient_branch_idx'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['payMode'], name='patient_paymode_idx'),
        ),
        migrations.AddIndex(
            model_name='admission',
            index=models.Index(fields=['patient', 'admNo'], name='admission_patient_admno_idx'),
        ),
        migrations.AddIndex(
            model_name='admission',
            index=models.Index(fields=['payMode'], name='admission_paymode_idx'),
        ),
        migrations.AddIndex(
            model_name='billing',
            index=models.Index(fields=['admission', 'printStatus'], name='billing_print_idx'),
        ),
    ]