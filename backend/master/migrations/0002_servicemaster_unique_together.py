# master/migrations/0002_servicemaster_unique_together.py
#
# Adds the unique_together constraint on master.ServiceMaster.
# ServiceMaster was deleted from the patients app in patients/0018
# and re-created in master/0001_initial. Schema changes to it must
# live in the master app.
#
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0001_initial'),
        # Ensures this runs after the patients/0022 chain completes
        ('patients', '0022_billing_onetoone_task_admission'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='servicemaster',
            unique_together={('description', 'pricing_type')},
        ),
    ]