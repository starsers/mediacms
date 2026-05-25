"""User permission assignments — admin grants access to members"""
from django.conf import settings
from django.db import models


class UserPermission(models.Model):
    """Admin-assigned permissions: member can access specific media/category/tag"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='permission_grants',
        help_text="Member receiving the permission",
    )
    # All three can be set (multi-select for admin)
    media = models.ManyToManyField(
        'files.Media',
        blank=True,
        related_name='user_permissions',
        help_text="Specific media items",
    )
    category = models.ManyToManyField(
        'files.Category',
        blank=True,
        related_name='user_permissions',
        help_text="Categories",
    )
    tags = models.ManyToManyField(
        'files.Tag',
        blank=True,
        related_name='user_permissions',
        help_text="All media with these tags",
    )
    can_download = models.BooleanField(default=False, help_text="Allow download")
    can_upload = models.BooleanField(default=False, help_text="Allow upload")
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='permissions_granted',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "User Permission"
        verbose_name_plural = "User Permissions"

    def __str__(self):
        parts = []
        if self.media.exists():
            parts.append(f"media:{self.media.count()}")
        if self.category.exists():
            parts.append(f"cat:{self.category.count()}")
        if self.tags.exists():
            parts.append(f"tags:{self.tags.count()}")
        scope = "+".join(parts) or "none"
        return f"{self.user.username} → {scope} (dl={self.can_download})"


class AccessRequest(models.Model):
    """Member requests access to media/category/tag — admin approves"""

    STATUS = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    SCOPE = (
        ('media', 'Single Media'),
        ('category', 'Entire Category'),
        ('tag', 'Tag'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='access_requests',
    )
    scope_type = models.CharField(max_length=20, choices=SCOPE, default='media')
    media = models.ForeignKey(
        'files.Media',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    category = models.ForeignKey(
        'files.Category',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    tag = models.ForeignKey(
        'files.Tag',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='access_requests_reviewed',
    )
    reason = models.TextField(blank=True, help_text="Reason for rejection")

    class Meta:
        verbose_name = "Access Request"
        verbose_name_plural = "Access Requests"
        ordering = ['-created_at']

    def __str__(self):
        scope = self.media or self.category or self.tag
        return f"{self.user.username} requested {self.scope_type}: {scope} [{self.status}]"
