from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('files', '0021_shared_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='media',
            name='approval_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('submitted', 'Submitted'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=20,
                db_index=True,
                help_text='Approval status',
            ),
        ),
    ]
