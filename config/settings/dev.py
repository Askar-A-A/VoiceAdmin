from .base import *

DEBUG = True
# The ngrok domains let CarrierX reach the dev server through an ngrok tunnel
# during live call testing. ('.ngrok-free.dev' is ngrok's current default.)
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.ngrok-free.dev', '.ngrok-free.app', '.ngrok.io']
CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.dev',
    'https://*.ngrok-free.app',
    'https://*.ngrok.io',
]
# ngrok terminates HTTPS and forwards to us over HTTP with this header. Trusting
# it makes Django build https:// callback URLs (the <Gather action="...">) so
# CarrierX posts digits back securely without a redirect.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
