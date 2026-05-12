from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0001_initial'),
        ('patients', '0019_admission_paymode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labreport',
            name='admission',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='lab_reports',
                to='patients.admission',
            ),
        ),
    ]