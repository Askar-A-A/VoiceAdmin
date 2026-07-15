from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

User = get_user_model()

_ctrl = {'class': 'form-control'}


class AccountSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'name']
        widgets = {
            'email': forms.EmailInput(attrs=_ctrl),
            'name': forms.TextInput(attrs=_ctrl),
        }


class PasswordUpdateForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs=_ctrl),
        label='Current password',
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs=_ctrl),
        label='New password',
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs=_ctrl),
        label='Confirm new password',
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        pw = self.cleaned_data.get('current_password')
        if not self.user.check_password(pw):
            raise forms.ValidationError('Current password is incorrect.')
        return pw

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('new_password') != cleaned_data.get('confirm_password'):
            raise forms.ValidationError('New passwords do not match.')
        return cleaned_data

    def save(self):
        self.user.set_password(self.cleaned_data['new_password'])
        self.user.save()
        return self.user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={**_ctrl, 'autofocus': True, 'placeholder': 'Email'}),
        label='Email',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={**_ctrl, 'placeholder': 'Password'}),
    )


class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs=_ctrl))
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs=_ctrl),
        label='Confirm password',
    )

    class Meta:
        model = User
        fields = ['email', 'name']
        widgets = {
            'email': forms.EmailInput(attrs={**_ctrl, 'placeholder': 'you@example.com'}),
            'name': forms.TextInput(attrs={**_ctrl, 'placeholder': 'Full name (optional)'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('confirm_password'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user
