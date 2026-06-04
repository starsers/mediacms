"""Permissions API — access requests, admin grants, permission checks"""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from files.models import Media, Category, Tag
from files.models.permissions import AccessRequest, UserPermission
from files.methods import notify_users
import json


def _check_can_approve(user):
    """Check if user is admin or configured reviewer"""
    reviewer = getattr(settings, 'APPROVAL_REVIEWER', 'admin')
    reviewers = [reviewer] if isinstance(reviewer, str) else reviewer
    return user.is_superuser or user.username in reviewers


def _serialize_access_request(access_request):
    """Serialize an access request for the admin approval UI."""
    return {
        'id': access_request.id,
        'user': access_request.user.username,
        'scope_type': access_request.scope_type,
        'media_id': access_request.media_id,
        'media_title': access_request.media.title if access_request.media else None,
        'category_id': access_request.category_id,
        'category_name': access_request.category.title if access_request.category else None,
        'tag_id': access_request.tag_id,
        'tag_name': access_request.tag.title if access_request.tag else None,
        'status': access_request.status,
        'reason': access_request.reason,
        'created_at': access_request.created_at.isoformat(),
        'reviewed_at': access_request.reviewed_at.isoformat() if access_request.reviewed_at else None,
        'reviewed_by': access_request.reviewed_by.username if access_request.reviewed_by else None,
    }


@csrf_exempt
@require_POST
@login_required
def request_access(request):
    """Member requests access to media/category/tag (download/clip)"""
    data = json.loads(request.body)
    scope_type = data.get('scope_type', 'media')
    media_id = data.get('media_id')
    category_id = data.get('category_id')
    tag_id = data.get('tag_id')

    if scope_type == 'category':
        if category_id and str(category_id).isdigit():
            category_id = int(category_id)
        else:
            category_uid = data.get('category_uid') or data.get('category_id')
            category = Category.objects.filter(uid=category_uid).first()
            if not category:
                return JsonResponse({'error': 'Category not found'}, status=404)
            category_id = category.id

    if scope_type == 'tag':
        if tag_id and str(tag_id).isdigit():
            tag_id = int(tag_id)
        else:
            tag_title = data.get('tag_title') or data.get('tag_id')
            tag = Tag.objects.filter(title=tag_title).first()
            if not tag:
                return JsonResponse({'error': 'Tag not found'}, status=404)
            tag_id = tag.id

    if scope_type == 'media' and media_id and str(media_id).isdigit():
        media_id = int(media_id)

    req = AccessRequest.objects.create(
        user=request.user,
        scope_type=scope_type,
        media_id=media_id,
        category_id=category_id,
        tag_id=tag_id,
        status='pending',
    )

    # Notify admin
    scope_desc = f"素材 #{req.media_id}" if scope_type == 'media' else \
                 f"分类 #{req.category_id}" if scope_type == 'category' else f"标签 #{req.tag_id}"
    notify_users(
        friendly_token=data.get('friendly_token', ''),
        action='access_requested',
        extra=f"{request.user.username}|{scope_type}|{scope_desc}",
    )

    return JsonResponse({'ok': True, 'id': req.id, 'status': 'pending'})


@csrf_exempt
@require_POST
@login_required
def request_upload_access(request):
    """Member requests upload permission (global, no scope)"""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Check if already has upload permission
    has_upload = UserPermission.objects.filter(
        user=request.user, can_upload=True
    ).exists()
    if has_upload:
        return JsonResponse({'ok': True, 'message': '已有上传权限'})

    pending = AccessRequest.objects.filter(
        user=request.user,
        scope_type='upload',
        status='pending',
    ).first()
    if pending:
        return JsonResponse({'ok': True, 'id': pending.id, 'status': pending.status, 'message': '上传权限申请已在审核中'})

    # Create a special access request (scope_type='upload')
    req = AccessRequest.objects.create(
        user=request.user,
        scope_type='upload',
        status='pending',
    )

    notify_users(
        action='access_requested',
        extra=f"{request.user.username}|upload|上传权限",
    )

    return JsonResponse({'ok': True, 'id': req.id, 'status': 'pending'})


@csrf_exempt
@require_POST
@login_required
def approve_access(request):
    """Admin approves or rejects an access request"""
    if not _check_can_approve(request.user):
        return JsonResponse({'error': 'Not authorized'}, status=403)

    data = json.loads(request.body)
    req_id = data.get('request_id')
    action = data.get('action')  # 'approve' or 'reject'
    reason = data.get('reason', '')

    try:
        req = AccessRequest.objects.get(id=req_id, status='pending')
    except AccessRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)

    if action == 'approve':
        # Create UserPermission (M2M fields via .add)
        perm_kwargs = dict(
            user=req.user,
            granted_by=request.user,
            can_download=data.get('can_download', True),
            can_upload=data.get('can_upload', False),
        )
        perm = UserPermission.objects.create(**perm_kwargs)
        if req.media:
            perm.media.add(req.media)
        if req.category:
            perm.category.add(req.category)
        if req.tag:
            perm.tags.add(req.tag)
        # upload scope: just set can_upload=True, no M2M needed
        if req.scope_type == 'upload':
            perm.can_upload = True
            perm.save(update_fields=['can_upload'])

        req.status = 'approved'
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        # Notify the requesting user
        notify_users(
            action='access_approved',
            extra=req.user.username,
        )

        return JsonResponse({'ok': True, 'status': 'approved'})

    elif action == 'reject':
        req.status = 'rejected'
        req.reviewed_by = request.user
        req.reason = reason
        req.reviewed_at = timezone.now()
        req.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'reason'])

        # Notify the requesting user
        notify_users(
            action='access_rejected',
            extra=req.user.username,
        )

        return JsonResponse({'ok': True, 'status': 'rejected', 'reason': reason})

    return JsonResponse({'error': 'Invalid action'}, status=400)


@csrf_exempt
@require_POST
@login_required
def grant_permission(request):
    """Admin directly grants permission to a member"""
    if not _check_can_approve(request.user):
        return JsonResponse({'error': 'Not authorized'}, status=403)

    data = json.loads(request.body)
    user_id = data.get('user_id')

    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    perm = UserPermission.objects.create(
        user=target_user,
        can_download=data.get('can_download', True),
        can_upload=data.get('can_upload', False),
        granted_by=request.user,
    )
    if data.get('media_ids'):
        perm.media.set(data['media_ids'])
    if data.get('category_ids'):
        perm.category.set(data['category_ids'])
    if data.get('tag_ids'):
        perm.tags.set(data['tag_ids'])

    return JsonResponse({'ok': True, 'id': perm.id})


@login_required
def pending_requests(request):
    """List access requests for admin approval UI."""
    if not _check_can_approve(request.user):
        return JsonResponse({'error': 'Not authorized'}, status=403)

    status_filter = request.GET.get('status', 'pending')
    requests_qs = AccessRequest.objects.select_related(
        'user', 'media', 'category', 'tag'
    )

    if status_filter != 'all':
        valid_statuses = {value for value, _label in AccessRequest.STATUS}
        if status_filter not in valid_statuses:
            status_filter = 'pending'
        requests_qs = requests_qs.filter(status=status_filter)

    counts = {
        status: AccessRequest.objects.filter(status=status).count()
        for status, _label in AccessRequest.STATUS
    }
    requests_qs = requests_qs.order_by('-created_at')[:100]

    return JsonResponse({
        'count': requests_qs.count(),
        'counts': counts,
        'results': [_serialize_access_request(r) for r in requests_qs],
    })


@login_required
def my_history(request):
    """List current user's access request history"""
    history = AccessRequest.objects.filter(user=request.user).select_related(
        'media', 'category', 'tag', 'reviewed_by'
    ).order_by('-created_at')[:50]

    return JsonResponse({
        'count': history.count(),
        'results': [
            {
                'id': r.id,
                'scope_type': r.scope_type,
                'media_title': r.media.title if r.media else None,
                'category_name': r.category.title if r.category else None,
                'tag_name': r.tag.title if r.tag else None,
                'status': r.status,
                'reason': r.reason,
                'created_at': r.created_at.isoformat(),
                'reviewed_at': r.reviewed_at.isoformat() if r.reviewed_at else None,
                'reviewed_by': r.reviewed_by.username if r.reviewed_by else None,
            }
            for r in history
        ]
    })


@login_required
def check_permission(request):
    """Check if user can view/download a specific media"""
    media_id = request.GET.get('media_id')
    if not media_id:
        return JsonResponse({'error': 'Missing media_id'}, status=400)

    # Admin/editor always have access
    if request.user.is_superuser or getattr(request.user, 'is_editor', False):
        return JsonResponse({'can_view': True, 'can_download': True})

    try:
        media = Media.objects.get(id=media_id)
    except Media.DoesNotExist:
        return JsonResponse({'error': 'Media not found'}, status=404)

    # Owners always have access
    if media.user == request.user:
        return JsonResponse({'can_view': True, 'can_download': True})

    # Check explicit permissions (M2M fields)
    perms = UserPermission.objects.filter(user=request.user)
    for p in perms:
        if p.media.filter(id=media_id).exists():
            return JsonResponse({'can_view': True, 'can_download': p.can_download})
        if p.category.filter(id__in=media.category.values_list('id', flat=True)).exists():
            return JsonResponse({'can_view': True, 'can_download': p.can_download})
        if p.tags.filter(id__in=media.tags.values_list('id', flat=True)).exists():
            return JsonResponse({'can_view': True, 'can_download': p.can_download})

    return JsonResponse({'can_view': False, 'can_download': False})


@login_required
def my_permissions(request):
    """List current user's permissions"""
    perms = UserPermission.objects.filter(user=request.user).prefetch_related('media', 'category', 'tags')

    return JsonResponse({
        'count': perms.count(),
        'results': [
            {
                'id': p.id,
                'media': [{'id': m.id, 'title': m.title} for m in p.media.all()],
                'categories': [{'id': c.id, 'title': c.title} for c in p.category.all()],
                'tags': [t.title for t in p.tags.all()],
                'can_download': p.can_download,
                'can_upload': p.can_upload,
            }
            for p in perms
        ]
    })
