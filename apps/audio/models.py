from django.db import models
from django.conf import settings


class AudioFile(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='audio_files',
    )
    name = models.CharField(max_length=255)
    file_sid = models.CharField(max_length=100, unique=True)
    container_sid = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name
    