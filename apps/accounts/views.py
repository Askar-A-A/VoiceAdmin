from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.views import View
from apps.audio.models import AudioFile
from .forms import RegisterForm, AccountSettingsForm, PasswordUpdateForm


class RegisterView(View):
    template_name = 'accounts/register.html'
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, self.template_name, {'form': RegisterForm()})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
        return render(request, self.template_name, {'form': form})


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('login')


@login_required
def account_settings(request):
    profile_form = AccountSettingsForm(instance=request.user)
    password_form = PasswordUpdateForm(user=request.user)

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = AccountSettingsForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated.')
                return redirect('account_settings')
        elif 'change_password' in request.POST:
            password_form = PasswordUpdateForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password changed.')
                return redirect('account_settings')

    stats = AudioFile.objects.filter(owner=request.user).aggregate(
        file_count=Count('id'),
        total_bytes=Sum('size_bytes'),
    )

    return render(request, 'accounts/settings.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'file_count': stats['file_count'] or 0,
        'total_bytes': stats['total_bytes'] or 0,
    })

    