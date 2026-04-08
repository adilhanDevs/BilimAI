from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('lessons', '0006_remove_stepmultiplechoice_allow_multiple'),
    ]

    operations = [
        migrations.AddField(
            model_name='stepmultiplechoice',
            name='source_unit',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='lessons.contentunit'),
        ),
    ]
