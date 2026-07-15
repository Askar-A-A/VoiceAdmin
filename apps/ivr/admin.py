from django.contrib import admin
from .models import Menu


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'key', 'menu_type', 'parent', 'created_at']
    list_filter = ['menu_type']
    search_fields = ['name', 'owner__email']
    readonly_fields = ['created_at']
