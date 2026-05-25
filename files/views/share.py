"""
Share API — Create, access, and manage shared media links.
"""

import logging

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Media, SharedLink

logger = logging.getLogger(__name__)


class ShareCreate(APIView):
    """Create a shareable link for a Media item."""

    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser,)

    def post(self, request, format=None):
        media_token = request.data.get('media_token', '')
        permission = request.data.get('permission', 'view')
        password = request.data.get('password', '')
        expires_days = request.data.get('expires_days')
        max_views = request.data.get('max_views')

        try:
            media = Media.objects.get(friendly_token=media_token)
        except Media.DoesNotExist:
            return Response({'error': 'Media not found'}, status=404)

        if media.user != request.user and not request.user.is_staff:
            return Response({'error': 'Not authorized'}, status=403)

        if permission not in dict(SharedLink.PERMISSION_LEVELS):
            permission = 'view'

        link = SharedLink.objects.create(
            media=media,
            created_by=request.user,
            permission=permission,
        )

        if password:
            link.set_password(password)

        if expires_days:
            try:
                days = int(expires_days)
                link.expires_at = timezone.now() + timezone.timedelta(days=days)
            except (ValueError, TypeError):
                pass

        if max_views:
            try:
                link.max_views = int(max_views)
            except (ValueError, TypeError):
                pass

        link.save()

        return Response({
            'token': str(link.token),
            'url': link.get_share_url(request),
            'permission': link.permission,
            'is_protected': link.is_protected,
            'expires_at': link.expires_at.isoformat() if link.expires_at else None,
        }, status=201)


class ShareAccess(APIView):
    """
    Access shared media via token.
    GET: verify token + require password if set
    POST: submit password to unlock
    """

    permission_classes = (permissions.AllowAny,)

    def get(self, request, token, format=None):
        link = get_object_or_404(SharedLink, token=token)

        if link.is_expired:
            return Response({'error': 'Link expired', 'expired': True}, status=410)

        # Check password if protected
        if link.is_protected:
            session_key = f'share_auth_{token}'
            if not request.session.get(session_key):
                return Response({
                    'requires_password': True,
                    'token': str(link.token),
                }, status=200)

        # Record access
        link.record_access()

        # Return media info based on permission
        media = link.media
        data = {
            'title': media.title,
            'description': media.description,
            'media_type': media.media_type,
            'ai_summary': media.ai_summary,
            'thumbnail_url': media.thumbnail_url if media.thumbnail_url else None,
            'permission': link.permission,
        }

        if link.permission in ('download', 'edit'):
            data['media_url'] = media.media_file.url if media.media_file else None

        return Response(data)

    def post(self, request, token, format=None):
        """Submit password to unlock."""
        link = get_object_or_404(SharedLink, token=token)

        if link.is_expired:
            return Response({'error': 'Link expired'}, status=410)

        password = request.data.get('password', '')
        if link.check_password(password):
            session_key = f'share_auth_{token}'
            request.session[session_key] = True
            return Response({'unlocked': True})

        return Response({'error': 'Wrong password'}, status=403)


class ShareList(APIView):
    """List and manage shares for current user."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, format=None):
        links = SharedLink.objects.filter(
            created_by=request.user
        ).select_related('media').order_by('-created_at')[:50]

        data = []
        for link in links:
            data.append({
                'token': str(link.token),
                'url': link.get_share_url(request),
                'media_title': link.media.title,
                'permission': link.permission,
                'is_protected': link.is_protected,
                'is_expired': link.is_expired,
                'view_count': link.view_count,
                'created_at': link.created_at.isoformat(),
                'expires_at': link.expires_at.isoformat() if link.expires_at else None,
            })

        return Response(data)

    def delete(self, request, format=None):
        token = request.data.get('token', '')
        try:
            link = SharedLink.objects.get(token=token, created_by=request.user)
            link.delete()
            return Response({'deleted': True})
        except SharedLink.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
