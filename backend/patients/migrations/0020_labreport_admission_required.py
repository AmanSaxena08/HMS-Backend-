from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0001_initial'),
        ('patients', '0019_admission_paymode'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DELETE FROM reports_labreport WHERE admission_id IS NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]