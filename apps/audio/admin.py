from django.contrib import admin
from .models import AudioFile, Folder


@admin.register(AudioFile)
class AudioFileAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'folder', 'file_sid', 'uploaded_at']
    list_filter = ['folder']
    search_fields = ['name', 'file_sid', 'owner__email']
    readonly_fields = ['file_sid', 'container_sid', 'uploaded_at']
    ordering = ['-uploaded_at']


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'created_at']
    search_fields = ['name', 'owner__email']
