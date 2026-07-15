import json
import requests
from django.conf import settings


def upload_to_carrierx(file_obj, filename):
    headers = {'Authorization': f'Bearer {settings.CARRIERX_ACCESS_TOKEN}'}
    container_sid = settings.CARRIERX_CONTAINER_SID
    file_object_meta = {
        'container_sid': container_sid,
        'name': filename,
        'type': 'audio',
    }
    files = {
        'file_object': (None, json.dumps(file_object_meta), 'application/json'),
        'data': (filename, file_obj, 'audio/mpeg'),
    }
    response = requests.post(
        'https://api.carrierx.com/core/v2/storage/files',
        headers=headers,
        files=files,
        timeout=300,
    )
    if response.status_code in [200, 201]:
        return response.json().get('file_sid')
    return None


def stream_from_carrierx(file_sid):
    headers = {'Authorization': f'Bearer {settings.CARRIERX_ACCESS_TOKEN}'}
    response = requests.get(
        f'https://api.carrierx.com/core/v2/storage/files/{file_sid}/data',
        headers=headers,
        stream=True,
        timeout=30,
    )
    return response


def delete_from_carrierx(file_sid):
    headers = {'Authorization': f'Bearer {settings.CARRIERX_ACCESS_TOKEN}'}
    response = requests.delete(
        f'https://api.carrierx.com/core/v2/storage/files/{file_sid}',
        headers=headers,
        timeout=30,
    )
    return response.status_code in [200, 204]
