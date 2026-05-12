from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0018_remove_departmentlogentry_created_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='admission',
            name='payMode',
            field=models.CharField(
                choices=[('cash', 'Cash'), ('cashless', 'Cashless')],
                default='cash',
                max_length=20,
            ),
        ),
    ]