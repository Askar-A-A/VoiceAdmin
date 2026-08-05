import random
from django.db import models
from django.conf import settings


class IVRConfig(models.Model):
    """Per-customer telephony settings.

    For the shared-number model, callers reach this customer's menu by
    entering `access_code`. `phone_number` is reserved for the future
    dedicated-number (paid) tier where no code is needed.
    """

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ivr_config',
    )
    access_code = models.CharField(max_length=10, unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.owner} ({self.access_code})'


def generate_unique_access_code():
    while True:
        code = f'{random.randint(0, 999999):06d}'
        if not IVRConfig.objects.filter(access_code=code).exists():
            return code


class Menu(models.Model):
    """A single voice box / extension in a customer's IVR tree.

    The root node (parent is null) is the main greeting — "extension 0".
    Every other node is reached from its parent by pressing `key`.
    """

    PLAYBACK_ONLY = 'playback'
    PLAYBACK_AND_RECORD = 'playback_record'
    DIAL_OUT = 'dial_out'
    TYPE_CHOICES = [
        (PLAYBACK_ONLY, 'Playback only'),
        (PLAYBACK_AND_RECORD, 'Playback & record message'),
        (DIAL_OUT, 'Dial out / forward'),
    ]

    KEY_CHOICES = [(str(d), str(d)) for d in range(1, 10)] + [('*', '*'), ('#', '#')]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='menus',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    key = models.CharField(
        max_length=1,
        choices=KEY_CHOICES,
        null=True,
        blank=True,
        help_text='Digit the caller presses to reach this menu from its parent.',
    )
    name = models.CharField(max_length=100)
    menu_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=PLAYBACK_ONLY)
    greeting = models.ForeignKey(
        'audio.AudioFile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='used_in_menus',
        help_text='Audio played when the caller enters this menu.',
    )
    dial_out_number = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['key']
        constraints = [
            models.UniqueConstraint(fields=['parent', 'key'], name='unique_key_per_parent'),
        ]

    def __str__(self):
        return self.name

    @property
    def is_root(self):
        return self.parent_id is None
