"""
Media Share — Token-based sharing with password protection and expiration.
Creates shareable links with configurable permissions (view/download/edit).
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.utils import timezone


class SharedLink(models.Model):
    """A shareable link for a Media item with optional password and expiration."""

    PERMISSION_LEVELS = (
        ('view', 'View Only'),
        ('download', 'View + Download'),
        ('edit', 'View + Download + Edit Metadata'),
    )

    token = models.UUIDField(
        default=uuid.uuid4, unique=True, db_index=True,
        help_text="Unique share token (UUID)"
    )
    media = models.ForeignKey(
        'Media', on_delete=models.CASCADE, related_name='shared_links'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Access control
    permission = models.CharField(
        max_length=20, choices=PERMISSION_LEVELS, default='view'
    )
    password = models.CharField(
        max_length=128, blank=True,
        help_text="Hashed password for access protection"
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Link expiration time (null = never)"
    )
    max_views = models.IntegerField(
        null=True, blank=True,
        help_text="Max number of times link can be accessed (null = unlimited)"
    )

    # Stats
    view_count = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Share:{self.media.title[:30]} — {self.token}"

    @property
    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        if self.max_views and self.view_count >= self.max_views:
            return True
        return False

    @property
    def is_protected(self):
        return bool(self.password)

    def set_password(self, raw_password: str):
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        if not self.password:
            return True  # No password set = open access
        return check_password(raw_password, self.password)

    def record_access(self):
        self.view_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['view_count', 'last_accessed'])

    def get_share_url(self, request=None):
        """Return the full share URL."""
        base = getattr(settings, 'SITE_URL', '')
        if not base and request:
            base = request.build_absolute_uri('/')[:-1]
        return f"{base}/share/{self.token}"
