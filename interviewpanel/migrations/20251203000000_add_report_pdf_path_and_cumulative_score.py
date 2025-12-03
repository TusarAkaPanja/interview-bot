# Generated migration for adding report_pdf_path and cumulative_score to InterviewSession

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interviewpanel', '20251202142417_20251202140634_interviewanswer_analysis_summary_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewsession',
            name='report_pdf_path',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='interviewsession',
            name='cumulative_score',
            field=models.FloatField(blank=True, default=0.0, null=True),
        ),
    ]

