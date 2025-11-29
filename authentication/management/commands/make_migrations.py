import os
import shutil
import datetime
from io import StringIO
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.conf import settings
from django.apps import apps

class Command(BaseCommand):
    help = 'Create migrations with a timestamp in the filename for a specific app'

    def add_arguments(self, parser):
        parser.add_argument('app_name', type=str, help='The name of the app to create migrations for')

    def handle(self, *args, **options):
        app_name = options.get('app_name')
        if not app_name:
            self.stderr.write(self.style.ERROR('App name is required'))
            return
        if not apps.is_installed(app_name):
            self.stderr.write(self.style.ERROR(f'App {app_name} is not installed'))
            return
        out = StringIO()
        err = StringIO()
        call_command('makemigrations', app_name, stdout=out, stderr=err)
        command_output = out.getvalue()
        error_output = err.getvalue()
        if 'No changes detected' in command_output:
            self.stdout.write(self.style.WARNING('No changes detected'))
            return
        migration_dir = os.path.join(settings.BASE_DIR, app_name, 'migrations')
        if not os.path.exists(migration_dir):
            self.stderr.write(self.style.ERROR(f'Migration directory {migration_dir} does not exist'))
            return
        migration_files = [f for f in os.listdir(migration_dir) if f.endswith('.py') and f != '__init__.py']
        if not migration_files:
            self.stderr.write(self.style.ERROR(f'No migration files found in {migration_dir}'))
            return
        latest_migration_file = max(migration_files, key=lambda x: os.path.getmtime(os.path.join(migration_dir, x)))
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        new_migration_file = f'{timestamp}_{latest_migration_file}'
        old_migration_file_path = os.path.join(migration_dir, latest_migration_file)
        new_migration_file_path = os.path.join(migration_dir, new_migration_file)
        shutil.move(old_migration_file_path, new_migration_file_path)
        self.stdout.write(self.style.SUCCESS(f'Migrations created successfully for {app_name}'))
