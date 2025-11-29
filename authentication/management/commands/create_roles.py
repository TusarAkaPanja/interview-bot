from django.core.management.base import BaseCommand
from authentication.models import Role


class Command(BaseCommand):
    help = 'Creates default roles: Superadmin, Admin, HR'

    def handle(self, *args, **options):
        roles = ['superadmin', 'admin', 'hr']
        
        for role_name in roles:
            role, created = Role.objects.get_or_create(name=role_name)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created role: {role_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Role already exists: {role_name}')
                )

