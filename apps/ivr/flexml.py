"""CarrierX FlexML call-control markup generation.

FlexML is CarrierX's TwiML-equivalent: an XML document the telephony platform
fetches from our webhook and executes (play audio, gather digits, dial, record).

NOTE: The verb/attribute names below follow TwiML conventions and should be
confirmed against CarrierX's FlexML docs (or the existing FlexMLIntegration
project). All XML lives here, so any syntax corrections are a one-file change.
"""
from xml.sax.saxutils import escape, quoteattr


def _document(inner):
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{inner}</Response>'


def gather_access_code(action_url, num_digits=6):
    """Prompt the caller for their access code and post it to action_url."""
    return _document(
        f'<Gather numDigits="{num_digits}" finishOnKey="#" action={quoteattr(action_url)} method="POST" timeout="8">'
        f'<Say>Please enter your access code, followed by the pound key.</Say>'
        f'</Gather>'
        f'<Say>We did not receive your code. Goodbye.</Say>'
        f'<Hangup/>'
    )


def play_and_gather(play_url, action_url):
    """Play this menu's greeting, then gather one digit to choose a sub-menu."""
    gather = f'<Gather numDigits="1" action={quoteattr(action_url)} method="POST" timeout="6">'
    if play_url:
        gather += f'<Play>{escape(play_url)}</Play>'
    gather += '</Gather>'
    # If no digit is pressed, fall through and hang up.
    return _document(gather + '<Hangup/>')


def play_only(play_url):
    """Play the greeting and end the call (a leaf playback box)."""
    inner = f'<Play>{escape(play_url)}</Play>' if play_url else ''
    return _document(inner + '<Hangup/>')


def dial(number):
    """Forward the caller to a phone number."""
    return _document(f'<Dial>{escape(number)}</Dial>')


def record(play_url, action_url, max_length=120):
    """Play the greeting, then record the caller's message."""
    inner = f'<Play>{escape(play_url)}</Play>' if play_url else ''
    inner += f'<Record action={quoteattr(action_url)} method="POST" maxLength="{max_length}"/>'
    return _document(inner)


def say(text):
    """Speak a system message and hang up."""
    return _document(f'<Say>{escape(text)}</Say><Hangup/>')
