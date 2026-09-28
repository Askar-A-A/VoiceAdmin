"""CarrierX FlexML call-control markup generation (ported verbatim).

FlexML is CarrierX's TwiML-equivalent: an XML document the telephony platform
fetches from our webhook and executes (play audio, gather digits, dial, record).
All XML lives here, so any syntax corrections are a one-file change.
"""
from xml.sax.saxutils import escape, quoteattr


def _document(inner: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{inner}</Response>'


def gather_access_code(action_url: str, num_digits: int = 6) -> str:
    return _document(
        f'<Gather numDigits="{num_digits}" finishOnKey="#" action={quoteattr(action_url)} method="POST" timeout="8">'
        f'<Say>Please enter your access code, followed by the pound key.</Say>'
        f'</Gather>'
        f'<Say>We did not receive your code. Goodbye.</Say>'
        f'<Hangup/>'
    )


def play_and_gather(play_url: str | None, action_url: str) -> str:
    gather = f'<Gather numDigits="1" action={quoteattr(action_url)} method="POST" timeout="6">'
    if play_url:
        gather += f'<Play>{escape(play_url)}</Play>'
    gather += '</Gather>'
    return _document(gather + '<Hangup/>')


def play_only(play_url: str | None) -> str:
    inner = f'<Play>{escape(play_url)}</Play>' if play_url else ''
    return _document(inner + '<Hangup/>')


def dial(number: str) -> str:
    return _document(f'<Dial>{escape(number)}</Dial>')


def record(play_url: str | None, action_url: str, max_length: int = 120) -> str:
    inner = f'<Play>{escape(play_url)}</Play>' if play_url else ''
    inner += f'<Record action={quoteattr(action_url)} method="POST" maxLength="{max_length}"/>'
    return _document(inner)


def say(text: str) -> str:
    return _document(f'<Say>{escape(text)}</Say><Hangup/>')
