from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


class ApprovalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.USERS_NEEDS_TO_BE_APPROVED and request.user.is_authenticated and not request.user.is_superuser and not getattr(request.user, 'is_approved', False):
            allowed_paths = [
                reverse('approval_required'),
                reverse('account_logout'),
            ]
            if request.path not in allowed_paths:
                if request.path.startswith('/api/'):
                    return JsonResponse({'detail': 'User account not approved.'}, status=403)
                return redirect('approval_required')

        response = self.get_response(request)
        return response


class IPWhitelistMiddleware:
    """Restrict access to specified IP addresses or ranges.
    Configure via IP_WHITELIST in settings (list of IP/CIDR).
    Empty list means no restriction. 127.0.0.1/localhost always allowed."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        whitelist = getattr(settings, 'IP_WHITELIST', [])
        if not whitelist:
            return self.get_response(request)

        client_ip = self._get_client_ip(request)
        if client_ip in ('127.0.0.1', '::1', 'localhost'):
            return self.get_response(request)

        if not self._ip_in_whitelist(client_ip, whitelist):
            if request.path.startswith('/api/'):
                return JsonResponse({'detail': 'IP not in whitelist'}, status=403)
            return JsonResponse({'detail': 'Access denied: IP not in whitelist'}, status=403)

        return self.get_response(request)

    def _get_client_ip(self, request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def _ip_in_whitelist(self, ip, whitelist):
        import ipaddress
        try:
            addr = ipaddress.ip_address(ip)
            for entry in whitelist:
                try:
                    if addr in ipaddress.ip_network(entry, strict=False):
                        return True
                except ValueError:
                    if ip == entry:
                        return True
        except ValueError:
            return ip in whitelist
        return False
