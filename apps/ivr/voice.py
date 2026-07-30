"""Public telephony webhook endpoints.

CarrierX calls these (no login, no CSRF) during a live phone call. Each view
returns FlexML telling CarrierX what to do next. Call state is carried in the
URLs (which menu we're in), so the endpoints are stateless.
"""
import json
import re

from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from apps.audio.services import stream_from_carrierx
from .models import Menu, IVRConfig
from . import flexml


def _no_cache(response):
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


def _xml(content):
    return _no_cache(HttpResponse(content, content_type='text/xml'))


def _param(request, name):
    """Read a callback parameter regardless of how CarrierX sends it.

    CarrierX may deliver the Gather/Record callback as POST form data, GET
    query params, or a JSON body depending on endpoint configuration.
    """
    if name in request.POST:
        return request.POST.get(name, '').strip()
    if name in request.GET:
        return request.GET.get(name, '').strip()
    if request.body:
        try:
            data = json.loads(request.body.decode('utf-8'))
            value = data.get(name)
            if value is not None:
                return str(value).strip()
        except (ValueError, AttributeError):
            pass
    return ''


def _play_url(request, menu):
    if not menu.greeting:
        return None
    return request.build_absolute_uri(reverse('voice_play', args=[menu.greeting.file_sid]))


def _render_menu(request, menu):
    """Turn one menu node into the FlexML for its behaviour."""
    play_url = _play_url(request, menu)

    if menu.menu_type == Menu.DIAL_OUT and menu.dial_out_number:
        return flexml.dial(menu.dial_out_number)

    if menu.menu_type == Menu.PLAYBACK_AND_RECORD:
        action = request.build_absolute_uri(reverse('voice_record', args=[menu.pk]))
        return flexml.record(play_url, action)

    # PLAYBACK_ONLY: play the greeting, and if there are sub-menus, gather a digit.
    if menu.children.exists():
        action = request.build_absolute_uri(reverse('voice_menu', args=[menu.pk]))
        return flexml.play_and_gather(play_url, action)
    return flexml.play_only(play_url)


def _digits_only(value):
    return re.sub(r'\D', '', value or '')


def _business_for_dialed_number(dialed):
    """Find the business whose own number matches the number that was dialed.

    Compares the last 10 digits so +1 / formatting differences don't matter.
    """
    dialed_digits = _digits_only(dialed)
    if not dialed_digits:
        return None
    for config in IVRConfig.objects.exclude(phone_number=''):
        if _digits_only(config.phone_number)[-10:] == dialed_digits[-10:]:
            return config
    return None


@csrf_exempt
def incoming_call(request):
    """Entry point CarrierX hits when a call arrives.

    If the dialed number belongs to a business, go straight to their menu.
    Otherwise fall back to the shared-number access-code prompt.
    """
    dialed = ''
    for key in ('To', 'Called', 'CalledNumber', 'DNIS', 'Destination', 'to', 'did', 'number'):
        dialed = _param(request, key)
        if dialed:
            break
    config = _business_for_dialed_number(dialed)
    if config:
        root = Menu.objects.filter(owner=config.owner, parent__isnull=True).first()
        if root:
            return _xml(_render_menu(request, root))
        return _xml(flexml.say('This number has no menu set up yet. Goodbye.'))

    action = request.build_absolute_uri(reverse('voice_access_code'))
    return _xml(flexml.gather_access_code(action))


@csrf_exempt
def access_code(request):
    digits = _param(request, 'Digits')
    try:
        config = IVRConfig.objects.get(access_code=digits)
    except IVRConfig.DoesNotExist:
        return _xml(flexml.say('That access code was not recognized. Goodbye.'))

    root = Menu.objects.filter(owner=config.owner, parent__isnull=True).first()
    if not root:
        return _xml(flexml.say('This account has no menu set up yet. Goodbye.'))
    return _xml(_render_menu(request, root))


@csrf_exempt
def menu_input(request, pk):
    """Caller pressed a digit while in menu `pk` — route to the matching child."""
    menu = get_object_or_404(Menu, pk=pk)
    digit = _param(request, 'Digits')
    child = menu.children.filter(key=digit).first()
    if child:
        return _xml(_render_menu(request, child))
    # Invalid choice — replay the current menu.
    return _xml(_render_menu(request, menu))


@csrf_exempt
def menu_record(request, pk):
    """Callback after a caller leaves a recording.

    A full implementation would persist request.POST['RecordingUrl'] (or the
    CarrierX file SID) as a Message tied to this menu. For now we acknowledge.
    """
    return _xml(flexml.say('Your message has been recorded. Goodbye.'))


def voice_play(request, file_sid):
    """Public audio stream CarrierX fetches to play a greeting.

    Unauthenticated by necessity (CarrierX can't log in). File SIDs are
    unguessable UUIDs; tightening this with a signed token is a later step.
    """
    response = stream_from_carrierx(file_sid)
    if response.status_code != 200:
        return HttpResponse(status=404)
    return _no_cache(StreamingHttpResponse(
        response.iter_content(chunk_size=8192),
        content_type=response.headers.get('Content-Type', 'audio/mpeg'),
    ))
