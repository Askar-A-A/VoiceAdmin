from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Menu, IVRConfig, generate_unique_access_code
from .forms import MenuForm
from .carrierx import list_phone_numbers


@login_required
def ivr_builder(request):
    root, _ = Menu.objects.get_or_create(
        owner=request.user,
        parent=None,
        defaults={'name': 'Main menu'},
    )
    config, _ = IVRConfig.objects.get_or_create(
        owner=request.user,
        defaults={'access_code': generate_unique_access_code()},
    )
    numbers = list_phone_numbers()
    return render(request, 'ivr/builder.html', {
        'root': root, 'config': config, 'numbers': numbers,
    })


@login_required
@require_POST
def set_phone_number(request):
    config, _ = IVRConfig.objects.get_or_create(
        owner=request.user,
        defaults={'access_code': generate_unique_access_code()},
    )
    config.phone_number = request.POST.get('phone_number', '').strip()
    config.save(update_fields=['phone_number'])
    messages.success(request, 'Phone number saved.')
    return redirect('ivr_builder')


@login_required
def menu_create(request, parent_pk):
    parent = get_object_or_404(Menu, pk=parent_pk, owner=request.user)
    if request.method == 'POST':
        form = MenuForm(request.POST, owner=request.user, parent=parent)
        if form.is_valid():
            menu = form.save(commit=False)
            menu.owner = request.user
            menu.parent = parent
            menu.save()
            messages.success(request, f'Added "{menu.name}".')
            return redirect('ivr_builder')
    else:
        form = MenuForm(owner=request.user, parent=parent)
    return render(request, 'ivr/menu_form.html', {
        'form': form, 'parent': parent, 'action': 'Add menu',
    })


@login_required
def menu_edit(request, pk):
    menu = get_object_or_404(Menu, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = MenuForm(request.POST, instance=menu, owner=request.user,
                        parent=menu.parent, is_root=menu.is_root)
        if form.is_valid():
            form.save()
            messages.success(request, 'Menu updated.')
            return redirect('ivr_builder')
    else:
        form = MenuForm(instance=menu, owner=request.user,
                        parent=menu.parent, is_root=menu.is_root)
    return render(request, 'ivr/menu_form.html', {
        'form': form, 'menu': menu, 'action': 'Edit menu',
    })


@login_required
@require_POST
def menu_delete(request, pk):
    menu = get_object_or_404(Menu, pk=pk, owner=request.user)
    if menu.is_root:
        messages.error(request, "The main menu can't be deleted.")
    else:
        name = menu.name
        menu.delete()
        messages.success(request, f'Removed "{name}".')
    return redirect('ivr_builder')
