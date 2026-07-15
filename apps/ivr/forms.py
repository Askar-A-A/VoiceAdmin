from django import forms
from apps.audio.models import AudioFile
from .models import Menu

_ctrl = {'class': 'form-control'}
_sel = {'class': 'form-select'}


class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ['key', 'name', 'menu_type', 'greeting', 'dial_out_number']
        widgets = {
            'key': forms.Select(attrs=_sel),
            'name': forms.TextInput(attrs={**_ctrl, 'placeholder': 'e.g. Sunday Service'}),
            'menu_type': forms.Select(attrs=_sel),
            'greeting': forms.Select(attrs=_sel),
            'dial_out_number': forms.TextInput(attrs={**_ctrl, 'placeholder': '+1 555 123 4567'}),
        }

    def __init__(self, *args, owner=None, parent=None, is_root=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_root = is_root

        # Only the owner's own audio files can be used as greetings.
        if owner is not None:
            self.fields['greeting'].queryset = AudioFile.objects.filter(owner=owner)
        self.fields['greeting'].empty_label = '— No greeting —'

        # The root (main menu) isn't reached by a key press; child nodes require one.
        if is_root:
            del self.fields['key']
        else:
            self.fields['key'].required = True
            if parent is not None:
                # So validate_unique can check (parent, key) on a new node.
                self.instance.parent = parent

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('menu_type') == Menu.DIAL_OUT and not cleaned.get('dial_out_number'):
            self.add_error('dial_out_number', 'A phone number is required for dial-out menus.')
        return cleaned
