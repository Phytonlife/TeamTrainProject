from django.core.management.base import BaseCommand
from backend.models import User # Make sure this import is correct for your project structure
import os

class Command(BaseCommand):
    """Django command to create a superuser if one doesn't exist."""

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not all([username, email, password]):
            self.stdout.write('Superuser environment variables not set. Skipping creation.')
            return

        if not User.objects.filter(username=username).exists():
            self.stdout.write(f'Creating superuser: {username}')
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser {username} created successfully.'))
        else:
            self.stdout.write(self.style.WARNING(f'Superuser {username} already exists.'))
