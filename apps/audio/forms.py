from django import forms
from django.conf import settings


class AudioUploadForm(forms.Form):
    name = forms.CharField(
        max_length=255,
        required=False,
        label='Display name',
        help_text='Optional — defaults to the filename if left blank.',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'My audio file'}),
    )
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'audio/*'}),
    )

    def clean_file(self):
        f = self.cleaned_data['file']
        max_size = getattr(settings, 'MAX_AUDIO_UPLOAD_SIZE', 50 * 1024 * 1024)
        if f.size > max_size:
            raise forms.ValidationError(f'File too large. Maximum size is {max_size // (1024 * 1024)} MB.')
        return f
