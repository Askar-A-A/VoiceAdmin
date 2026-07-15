"""CarrierX telephony API helpers (phone numbers / DIDs)."""
import requests
from django.conf import settings


def list_phone_numbers():
    """Return the phone numbers (DIDs) rented on the CarrierX account.

    Returns a list of number strings; an empty list on any failure so the
    page still renders.
    """
    headers = {'Authorization': f'Bearer {settings.CARRIERX_ACCESS_TOKEN}'}
    try:
        response = requests.get(
            'https://api.carrierx.com/core/v2/phonenumber/dids',
            headers=headers,
            timeout=10,
        )
    except requests.RequestException:
        return []

    if response.status_code != 200:
        return []

    data = response.json()
    items = data.get('items', []) if isinstance(data, dict) else data

    numbers = []
    for item in items:
        number = item.get('phonenumber') or item.get('did') or item.get('number')
        if number:
            numbers.append(number)
    return numbers
