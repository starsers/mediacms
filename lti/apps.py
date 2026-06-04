from django.apps import AppConfig
from django.db.models.signals import post_migrate

from .keys import ensure_keys_exist


def _ensure_lti_keys(sender, **kwargs):
    """Ensure LTI key pair exists after migrations."""
    try:
        ensure_keys_exist()
    except Exception:
        pass


class LtiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lti'
    verbose_name = 'LTI 1.3 Integration'

    def ready(self):
        post_migrate.connect(_ensure_lti_keys, sender=self)
