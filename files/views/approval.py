"""Approval API: submit, approve, reject, notifications, and media tools."""
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from files.methods import notify_users
from files.models import Media


def _get_approval_reviewer():
    """Get configured approval reviewer username(s)."""
    reviewer = getattr(settings, "APPROVAL_REVIEWER", "admin")
    if isinstance(reviewer, str):
        return [reviewer]
    return reviewer


def _load_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


@csrf_exempt
@require_POST
@login_required
def submit_for_approval(request):
    """Uploader submits media for approval."""
    data = _load_json_body(request)
    friendly_token = data.get("friendly_token") or data.get("id")

    if not friendly_token:
        return JsonResponse({"error": "Missing friendly_token"}, status=400)

    media = get_object_or_404(Media, friendly_token=friendly_token)
    if media.user != request.user:
        return JsonResponse({"error": "Not your media"}, status=403)

    if media.approval_status not in ("pending", "rejected"):
        return JsonResponse({"error": f"Already {media.approval_status}"}, status=400)

    media.approval_status = "submitted"
    media.save(update_fields=["approval_status"])

    notify_users(
        friendly_token=friendly_token,
        action="media_submitted_for_approval",
        extra=media.user.username,
    )

    return JsonResponse({
        "ok": True,
        "approval_status": media.approval_status,
        "message": "已提交审批，请等待管理员审核",
    })


@csrf_exempt
@require_POST
@login_required
def approve_media(request):
    """Reviewer approves media and makes it listable."""
    data = _load_json_body(request)
    friendly_token = data.get("friendly_token") or data.get("id")

    if not friendly_token:
        return JsonResponse({"error": "Missing friendly_token"}, status=400)

    reviewers = _get_approval_reviewer()
    if request.user.username not in reviewers and not request.user.is_superuser:
        return JsonResponse({"error": "Not an approval reviewer"}, status=403)

    media = get_object_or_404(Media, friendly_token=friendly_token)
    if media.approval_status != "submitted":
        return JsonResponse({"error": f"Not in submitted state (current: {media.approval_status})"}, status=400)

    media.approval_status = "approved"
    media.is_reviewed = True
    media.listable = True
    media.save(update_fields=["approval_status", "is_reviewed", "listable"])

    notify_users(
        friendly_token=friendly_token,
        action="media_approved",
        extra=request.user.username,
    )

    return JsonResponse({
        "ok": True,
        "approval_status": media.approval_status,
        "listable": media.listable,
        "message": "审批通过，素材已公开",
    })


@csrf_exempt
@require_POST
@login_required
def reject_media(request):
    """Reviewer rejects media."""
    data = _load_json_body(request)
    friendly_token = data.get("friendly_token") or data.get("id")
    reason = data.get("reason", "未说明原因")

    if not friendly_token:
        return JsonResponse({"error": "Missing friendly_token"}, status=400)

    reviewers = _get_approval_reviewer()
    if request.user.username not in reviewers and not request.user.is_superuser:
        return JsonResponse({"error": "Not an approval reviewer"}, status=403)

    media = get_object_or_404(Media, friendly_token=friendly_token)
    if media.approval_status != "submitted":
        return JsonResponse({"error": f"Not in submitted state (current: {media.approval_status})"}, status=400)

    media.approval_status = "rejected"
    media.save(update_fields=["approval_status"])

    notify_users(
        friendly_token=friendly_token,
        action="media_rejected",
        extra=reason,
    )

    return JsonResponse({
        "ok": True,
        "approval_status": media.approval_status,
        "message": "已驳回",
        "reason": reason,
    })


@login_required
def pending_approvals(request):
    """List media pending approval for reviewers."""
    reviewers = _get_approval_reviewer()
    if request.user.username not in reviewers and not request.user.is_superuser:
        return JsonResponse({"error": "Not an approval reviewer"}, status=403)

    pending = Media.objects.filter(
        approval_status="submitted",
    ).select_related("user").order_by("-add_date")[:50]

    return JsonResponse({
        "count": pending.count(),
        "results": [
            {
                "friendly_token": media.friendly_token,
                "title": media.title,
                "media_type": media.media_type,
                "user": media.user.username,
                "add_date": media.add_date.isoformat(),
                "approval_status": media.approval_status,
                "url": media.get_absolute_url(),
            }
            for media in pending
        ],
    })


@csrf_exempt
@login_required
@require_POST
def toggle_archive(request, friendly_token):
    """Archive or unarchive own media."""
    media = get_object_or_404(Media, friendly_token=friendly_token)
    if media.user != request.user and not request.user.is_superuser:
        return JsonResponse({"ok": False, "error": "permission denied"}, status=403)

    action = _load_json_body(request).get("action", "archive")
    media.is_archived = action == "archive"
    media.save(update_fields=["is_archived"])
    return JsonResponse({"ok": True, "is_archived": media.is_archived})


@csrf_exempt
@login_required
@require_POST
def trigger_transcribe(request, friendly_token):
    """Trigger VideoCaptioner subtitle generation for video/audio."""
    media = get_object_or_404(Media, friendly_token=friendly_token)
    if media.media_type not in ("video", "audio"):
        return JsonResponse({"ok": False, "error": "only video/audio supported"}, status=400)
    if media.subtitles.exists():
        return JsonResponse({"ok": False, "error": "subtitles already exist"}, status=400)
    if not getattr(settings, "USE_VIDEOCAPTIONER_TRANSCRIBE", False):
        return JsonResponse({"ok": False, "error": "subtitle generation backend is disabled"}, status=503)
    if media.videocaptioner_requests.filter(status__in=("pending", "running")).exists():
        return JsonResponse({"ok": False, "error": "subtitle generation already running"}, status=400)

    from files.models import Language, VideoCaptionerRequest
    from files.tasks import video_captioner_transcribe

    language, _ = Language.objects.update_or_create(
        code=getattr(settings, "VIDEOCAPTIONER_SUBTITLE_LANGUAGE_CODE", "zh-Hans"),
        defaults={"title": getattr(settings, "VIDEOCAPTIONER_SUBTITLE_LANGUAGE_TITLE", "简体中文")},
    )
    request_obj = VideoCaptionerRequest.objects.create(
        media=media,
        language=language,
        asr=getattr(settings, "VIDEOCAPTIONER_ASR", "bijian"),
        source_language=getattr(settings, "VIDEOCAPTIONER_LANGUAGE", "auto"),
    )
    task = video_captioner_transcribe.apply_async(args=[request_obj.id], countdown=1)
    return JsonResponse({"ok": True, "task_id": task.id, "message": "subtitle generation started"})


@csrf_exempt
@login_required
@require_POST
def trigger_denoise(request, friendly_token):
    """Trigger FFmpeg noise reduction."""
    media = get_object_or_404(Media, friendly_token=friendly_token)
    if media.media_type not in ("video", "audio"):
        return JsonResponse({"ok": False, "error": "only video/audio supported"}, status=400)

    from files.tasks import denoise_media

    task = denoise_media.delay(media.friendly_token)
    return JsonResponse({"ok": True, "task_id": task.id, "message": "denoise started"})


def notification_count(request):
    """Return unread notification count for the bell badge."""
    if request.user.is_anonymous:
        return JsonResponse({"count": 0})

    count = request.user.notifications.filter(notify=True).count()
    return JsonResponse({"count": count})


@login_required
def notification_list(request):
    """Return user's notifications with links."""
    notifications = request.user.notifications.filter(notify=True).order_by("-created_at")[:50]

    action_labels = {
        "access_requested": "新的权限申请",
        "access_approved": "权限申请已通过",
        "access_rejected": "权限申请已驳回",
        "media_submitted_for_approval": "新素材待审批",
        "media_approved": "素材已通过审批",
        "media_rejected": "素材已驳回",
        "important_media": "重要素材标记",
    }

    results = []
    for notification in notifications:
        results.append({
            "id": notification.id,
            "action": notification.action,
            "label": action_labels.get(notification.action, notification.action),
            "link": notification.link or "",
            "created_at": notification.created_at.isoformat() if notification.created_at else "",
        })

    return JsonResponse({"count": len(results), "results": results})


@csrf_exempt
@require_POST
@login_required
def notification_mark_read(request):
    """Mark all notifications as read."""
    request.user.notifications.filter(notify=True).update(notify=False)
    return JsonResponse({"ok": True})
