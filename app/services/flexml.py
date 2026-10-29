"""CarrierX FlexML call-control markup generation (ported verbatim).

FlexML is CarrierX's TwiML-equivalent: an XML document the telephony platform
fetches from our webhook and executes (play audio, gather digits, dial, record).
All XML lives here, so any syntax corrections are a one-file change.
"""
from xml.sax.saxutils import escape, quoteattr


def _document(inner: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{inner}</Response>'


# How long (seconds) we wait for a key press after the prompt ends.
MENU_TIMEOUT = 15      # caller menus
CODE_TIMEOUT = 20      # access code / PIN (people look it up or type slowly)
ADMIN_TIMEOUT = 20     # owner's admin menu
PLAYER_TIMEOUT = 30    # after a voicemail has been read out


def _no_input_tail(retry_url: str | None, goodbye: str | None) -> str:
    """What happens when nobody pressed anything.

    With a retry_url we send the call back to the same step (the server counts the
    repeats and gives up after a few); without it we say goodbye and hang up.
    """
    if retry_url:
        return f'<Redirect>{escape(retry_url)}</Redirect>'
    say = f'<Say>{escape(goodbye)}</Say>' if goodbye else ''
    return say + '<Hangup/>'


def gather_access_code(action_url: str, num_digits: int = 6, retry_url: str | None = None) -> str:
    return _document(
        f'<Gather numDigits="{num_digits}" finishOnKey="#" action={quoteattr(action_url)} method="POST" timeout="{CODE_TIMEOUT}">'
        f'<Say>Please enter your access code, followed by the pound key.</Say>'
        f'</Gather>'
        + _no_input_tail(retry_url, "We did not receive your code. Goodbye.")
    )


def play_and_gather(play_url: str | None, action_url: str, retry_url: str | None = None) -> str:
    gather = f'<Gather numDigits="1" action={quoteattr(action_url)} method="POST" timeout="{MENU_TIMEOUT}">'
    if play_url:
        gather += f'<Play>{escape(play_url)}</Play>'
    gather += '</Gather>'
    return _document(gather + _no_input_tail(retry_url, None))


def play_only(play_url: str | None) -> str:
    inner = f'<Play>{escape(play_url)}</Play>' if play_url else ''
    return _document(inner + '<Hangup/>')


def dial(number: str) -> str:
    return _document(f'<Dial>{escape(number)}</Dial>')


def record(
    play_url: str | None,
    action_url: str,
    max_length: int = 120,
    say_text: str | None = None,
    container_sid: str | None = None,
    callback_url: str | None = None,
    finish_on_key: str | None = None,
) -> str:
    """CarrierX FlexML <Record>.

    `finish_on_key`: the only key that ends the recording (without it, any key does).

    Unlike TwiML, CarrierX saves nothing unless the recording has a storage
    container (`containerSid`). `action` returns the next instructions once the
    recording ends; `callbackUrl` receives the recording data after the call ends
    (RecordingFileSid, RecordingUrl, ...) — it is what catches callers who hang up
    mid-recording, when `action` is never requested.
    """
    inner = f'<Play>{escape(play_url)}</Play>' if play_url else ''
    if say_text:
        inner += f'<Say>{escape(say_text)}</Say>'
    attrs = f'action={quoteattr(action_url)} method="POST" maxLength="{max_length}" playBeep="true"'
    if container_sid:
        attrs += f' containerSid={quoteattr(container_sid)}'
    if callback_url:
        attrs += f' callbackUrl={quoteattr(callback_url)}'
    inner += f'<Record {attrs}></Record>'
    return _document(inner)


def gather_pin(action_url: str, prompt: str, retry_url: str | None = None) -> str:
    """Ask the owner for their PIN (digits, ended with #)."""
    return _document(
        f'<Gather numDigits="8" finishOnKey="#" action={quoteattr(action_url)} method="POST" timeout="{CODE_TIMEOUT}">'
        f'<Say>{escape(prompt)}</Say>'
        f'</Gather>'
        + _no_input_tail(retry_url, "We did not receive your PIN. Goodbye.")
    )


def admin_menu(action_url: str, intro: str, retry_url: str | None = None) -> str:
    """The owner's menu; one key press chooses."""
    return _document(
        f'<Gather numDigits="1" action={quoteattr(action_url)} method="POST" timeout="{ADMIN_TIMEOUT}">'
        f'<Say>{escape(intro)}</Say>'
        f'</Gather>'
        + _no_input_tail(retry_url, "Goodbye.")
    )


def message_player(action_url: str, intro: str, play_url: str | None, prompt: str) -> str:
    """Announce a voicemail, play it, then list the keys. Keys work while it plays."""
    gather = f'<Gather numDigits="1" action={quoteattr(action_url)} method="POST" timeout="{PLAYER_TIMEOUT}">'
    gather += f'<Say>{escape(intro)}</Say>'
    if play_url:
        gather += f'<Play>{escape(play_url)}</Play>'
    gather += f'<Say>{escape(prompt)}</Say></Gather>'
    return _document(gather + '<Say>Goodbye.</Say><Hangup/>')


def say(text: str) -> str:
    return _document(f'<Say>{escape(text)}</Say><Hangup/>')


def review_menu(action_url: str, play_url: str | None = None) -> str:
    """Post-recording menu; `play_url` plays the caller's own message back first."""
    gather = f'<Gather numDigits="1" action={quoteattr(action_url)} method="POST" timeout="8">'
    if play_url:
        gather += f'<Play>{escape(play_url)}</Play>'
    gather += (
        '<Say>To listen to your message, press 1. To delete it and record again, press 2. '
        'To send it, just hang up.</Say>'
        '</Gather>'
    )
    return _document(gather + '<Say>Your message has been saved. Goodbye.</Say><Hangup/>')
