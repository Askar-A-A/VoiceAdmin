import requests
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Create a new CarrierX storage container for this portal'

    def add_arguments(self, parser):
        parser.add_argument('--name', default='voiceadmin-portal', help='Container name')

    def handle(self, *args, **options):
        name = options['name']
        headers = {
            'Authorization': f'Bearer {settings.CARRIERX_ACCESS_TOKEN}',
            'Content-Type': 'application/json',
        }

        self.stdout.write(f'Creating container "{name}"...')

        response = requests.post(
            'https://api.carrierx.com/core/v2/storage/containers',
            headers=headers,
            json={'name': name},
            timeout=30,
        )

        if response.status_code in [200, 201]:
            data = response.json()
            container_sid = data.get('container_sid')
            self.stdout.write(self.style.SUCCESS(f'\nContainer created successfully.'))
            self.stdout.write(f'  Name:          {data.get("name")}')
            self.stdout.write(f'  Container SID: {container_sid}')
            self.stdout.write(self.style.WARNING(f'\nAdd this to your .env:'))
            self.stdout.write(f'  CARRIERX_CONTAINER_SID={container_sid}')
        else:
            self.stdout.write(self.style.ERROR(f'Failed: HTTP {response.status_code}'))
            self.stdout.write(response.text)
