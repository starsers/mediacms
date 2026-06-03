import json
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from html import escape
from xml.etree import ElementTree as ET

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.http import FileResponse, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils.html import mark_safe, strip_tags
from django.views.decorators.csrf import csrf_exempt

from cms.version import VERSION
from files.methods import user_allowed_to_upload
from users.models import User

from .. import helpers
from ..forms import (
    ContactForm,
    EditSubtitleForm,
    MediaMetadataForm,
    MediaPublishForm,
    ReplaceMediaForm,
    SubtitleForm,
    WhisperSubtitlesForm,
)
from ..frontend_translations import translate_string
from ..helpers import get_alphanumeric_and_spaces
from ..methods import (
    can_transcribe_video,
    create_video_trim_request,
    get_user_or_session,
    handle_video_chapters,
    is_media_allowed_type,
    is_mediacms_editor,
)
from ..models import Category, Media, Page, Playlist, Subtitle, Tag, VideoTrimRequest
from ..tasks import save_user_action, video_trim_task
from ..waic_categories import waic_fixed_category_options, waic_fixed_category_queryset

WAIC_OFFICE_PDF_EXTENSIONS = {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xlsm", ".xls"}


def _waic_xml_text_nodes(root):
    texts = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            texts.append(node.text)
    return texts


def _waic_preview_shell(title, body, kind="DOCUMENT_PREVIEW"):
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{
  margin: 0;
  padding: 24px;
  background: #f8fafc;
  color: #0f172a;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.preview-wrap {{
  max-width: 1080px;
  margin: 0 auto;
}}
.preview-kicker {{
  display: inline-flex;
  height: 26px;
  align-items: center;
  padding: 0 10px;
  border: 1px solid rgba(26,86,219,.18);
  border-radius: 8px;
  color: #1a56db;
  font: 800 11px/1 "JetBrains Mono", Consolas, monospace;
}}
h1 {{
  margin: 12px 0 20px;
  font-size: 24px;
  line-height: 1.28;
}}
.doc, .sheet, .slides, .text-preview {{
  border: 1px solid rgba(30,58,95,.12);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 18px 38px rgba(15,23,42,.08);
  overflow: hidden;
}}
.doc {{
  padding: 28px 34px;
  font-size: 15px;
  line-height: 1.85;
}}
.doc p {{ margin: 0 0 12px; }}
.slide {{
  margin: 18px;
  padding: 22px;
  border: 1px solid rgba(30,58,95,.1);
  border-radius: 8px;
  background: #fff;
}}
.slide h2 {{ margin: 0 0 14px; font-size: 16px; color: #1a56db; }}
.slide p {{ margin: 0 0 8px; line-height: 1.7; }}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
th, td {{
  padding: 9px 10px;
  border: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
}}
th {{ background: #eff6ff; color: #1e3a5f; }}
pre {{
  margin: 0;
  padding: 22px;
  max-height: 82vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font: 13px/1.65 "JetBrains Mono", Consolas, monospace;
}}
.empty {{
  padding: 40px;
  color: #64748b;
  text-align: center;
}}
</style>
</head>
<body>
<main class="preview-wrap">
  <span class="preview-kicker">{escape(kind)}</span>
  <h1>{escape(title or "未命名素材")}</h1>
  {body}
</main>
</body>
</html>"""


def _waic_docx_preview(path):
    paragraphs = []
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    for para in root.iter():
        if not para.tag.endswith("}p"):
            continue
        text = "".join(_waic_xml_text_nodes(para)).strip()
        if text:
            paragraphs.append(f"<p>{escape(text)}</p>")
    if not paragraphs:
        return '<div class="empty">未读取到可预览文本。</div>'
    return '<div class="doc">' + "\n".join(paragraphs[:1200]) + "</div>"


def _waic_pptx_preview(path):
    slides = []
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            [name for name in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
            key=lambda value: int(re.search(r"slide(\d+)\.xml$", value).group(1)),
        )
        for index, name in enumerate(slide_names[:80], start=1):
            root = ET.fromstring(archive.read(name))
            texts = [text.strip() for text in _waic_xml_text_nodes(root) if text.strip()]
            if texts:
                body = "".join(f"<p>{escape(text)}</p>" for text in texts)
            else:
                body = '<p class="empty">此页未读取到文本内容。</p>'
            slides.append(f'<section class="slide"><h2>Slide {index}</h2>{body}</section>')
    if not slides:
        return '<div class="empty">未读取到可预览幻灯片。</div>'
    return '<div class="slides">' + "\n".join(slides) + "</div>"


def _waic_xlsx_preview(path):
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.iter():
                if item.tag.endswith("}si"):
                    shared.append("".join(_waic_xml_text_nodes(item)))
        sheet_names = [name for name in archive.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", name)]
        if not sheet_names:
            return '<div class="empty">未读取到工作表。</div>'
        root = ET.fromstring(archive.read(sorted(sheet_names)[0]))

    rows = []
    for row in root.iter():
        if not row.tag.endswith("}row"):
            continue
        cells = []
        for cell in row:
            if not cell.tag.endswith("}c"):
                continue
            cell_type = cell.attrib.get("t")
            value = ""
            if cell_type == "inlineStr":
                value = "".join(_waic_xml_text_nodes(cell))
            else:
                value_node = next((child for child in cell if child.tag.endswith("}v")), None)
                if value_node is not None and value_node.text is not None:
                    value = value_node.text
                    if cell_type == "s" and value.isdigit():
                        idx = int(value)
                        value = shared[idx] if idx < len(shared) else value
            cells.append(f"<td>{escape(value)}</td>")
        if cells:
            rows.append("<tr>" + "".join(cells[:30]) + "</tr>")
        if len(rows) >= 300:
            break
    if not rows:
        return '<div class="empty">未读取到可预览表格内容。</div>'
    return '<div class="sheet"><table><tbody>' + "\n".join(rows) + "</tbody></table></div>"


def _waic_text_preview(path):
    with open(path, "rb") as handle:
        data = handle.read(512000)
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = ""
    return '<div class="text-preview"><pre>' + escape(text) + "</pre></div>"


def _waic_find_office_converter():
    for executable in ("libreoffice", "soffice"):
        path = shutil.which(executable)
        if path:
            return path
    return None


def _waic_office_pdf_path(media, source_path):
    converter = _waic_find_office_converter()
    if not converter:
        raise RuntimeError("LibreOffice is not installed in this runtime.")

    stat = os.stat(source_path)
    cache_key = f"{media.friendly_token}:{source_path}:{stat.st_size}:{int(stat.st_mtime)}"
    cache_hash = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:16]
    cache_name = f"{media.friendly_token}-{cache_hash}.pdf"
    cache_root = getattr(settings, "TEMP_DIRECTORY", None) or tempfile.gettempdir()
    if not os.path.isdir(cache_root):
        cache_root = tempfile.gettempdir()
    cache_dir = os.path.join(cache_root, "waic_previews")
    os.makedirs(cache_dir, exist_ok=True)
    cached_pdf = os.path.join(cache_dir, cache_name)
    if os.path.exists(cached_pdf):
        return cached_pdf

    tmp_parent = getattr(settings, "TEMP_DIRECTORY", None) or tempfile.gettempdir()
    if not os.path.isdir(tmp_parent):
        tmp_parent = tempfile.gettempdir()
    work_dir = tempfile.mkdtemp(prefix="waic-office-", dir=tmp_parent)
    profile_dir = tempfile.mkdtemp(prefix="waic-lo-", dir=tmp_parent)
    try:
        command = [
            converter,
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--norestore",
            f"-env:UserInstallation=file://{profile_dir.replace(os.sep, '/')}",
            "--convert-to",
            "pdf",
            "--outdir",
            work_dir,
            source_path,
        ]
        completed = subprocess.run(
            command,
            check=False,
            timeout=90,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "LibreOffice conversion failed.").strip()
            raise RuntimeError(message[-500:])

        generated = [
            os.path.join(work_dir, filename)
            for filename in os.listdir(work_dir)
            if filename.lower().endswith(".pdf")
        ]
        if not generated:
            raise RuntimeError("LibreOffice did not produce a PDF file.")
        shutil.move(generated[0], cached_pdf)
        return cached_pdf
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        shutil.rmtree(profile_dir, ignore_errors=True)


def get_page(request, slug):
    context = {}
    page = Page.objects.filter(slug=slug).first()
    if page:
        context["page"] = page
    else:
        return render(request, "404.html", context)
    return render(request, "cms/page.html", context)


@login_required
def record_screen(request):
    """Record screen view"""

    context = {}
    context["can_add"] = user_allowed_to_upload(request)
    can_upload_exp = settings.CANNOT_ADD_MEDIA_MESSAGE
    context["can_upload_exp"] = can_upload_exp

    return render(request, "cms/record_screen.html", context)


def about(request):
    """About view"""

    page = Page.objects.filter(slug="about").first()
    if page:
        context = {}
        context["page"] = page
        return render(request, "cms/page.html", context)

    context = {"VERSION": VERSION}
    return render(request, "cms/about.html", context)


def approval_required(request):
    """User needs approval view"""
    return render(request, "cms/user_needs_approval.html", {})


def setlanguage(request):
    """Set Language view"""

    context = {}
    return render(request, "cms/set_language.html", context)


@login_required
def add_subtitle(request):
    """Add subtitle view"""

    friendly_token = request.GET.get("m", "").strip()
    if not friendly_token:
        return HttpResponseRedirect("/")

    media = Media.objects.filter(friendly_token=friendly_token).first()
    if not media:
        return HttpResponseRedirect("/")

    if not (is_mediacms_editor(request.user) or request.user.has_contributor_access_to_media(media)):
        return HttpResponseRedirect("/")

    # Initialize variables
    form = None
    whisper_form = None
    show_whisper_form = can_transcribe_video(request.user)

    if request.method == "POST":
        if 'submit' in request.POST:
            form = SubtitleForm(media, request.POST, request.FILES, prefix="form")
            if form.is_valid():
                subtitle = form.save()
                try:
                    subtitle.convert_to_srt()
                    messages.add_message(request, messages.INFO, "Caption was added!")
                    return HttpResponseRedirect(subtitle.media.get_absolute_url())
                except Exception as e:  # noqa
                    subtitle.delete()
                    error_msg = "Invalid subtitle format. Use SubRip (.srt) or WebVTT (.vtt) files."
                    form.add_error("subtitle_file", error_msg)

        elif 'submit_whisper' in request.POST and show_whisper_form:
            whisper_form = WhisperSubtitlesForm(request.user, request.POST, instance=media, prefix="whisper_form")
            if whisper_form.is_valid():
                whisper_form.save()
                messages.add_message(request, messages.INFO, "Request for transcription was sent")
                return HttpResponseRedirect(media.get_absolute_url())

    # GET request or form invalid
    if form is None:
        form = SubtitleForm(media_item=media, prefix="form")

    if show_whisper_form and whisper_form is None:
        whisper_form = WhisperSubtitlesForm(request.user, instance=media, prefix="whisper_form")

    subtitles = media.subtitles.all()
    context = {"media_object": media, "form": form, "subtitles": subtitles, "whisper_form": whisper_form}
    return render(request, "cms/add_subtitle.html", context)


@login_required
def edit_subtitle(request):
    subtitle_id = request.GET.get("id", "").strip()
    action = request.GET.get("action", "").strip()
    if not subtitle_id:
        return HttpResponseRedirect("/")
    subtitle = Subtitle.objects.filter(id=subtitle_id).first()

    if not subtitle:
        return HttpResponseRedirect("/")

    if not (is_mediacms_editor(request.user) or request.user.has_contributor_access_to_media(subtitle.media)):
        return HttpResponseRedirect("/")

    context = {"subtitle": subtitle, "action": action}

    if action == "download":
        response = HttpResponse(subtitle.subtitle_file.read(), content_type="text/vtt")
        filename = subtitle.subtitle_file.name.split("/")[-1]

        if not filename.endswith(".vtt"):
            filename = f"{filename}.vtt"

        response["Content-Disposition"] = f"attachment; filename={filename}"  # noqa

        return response

    if request.method == "GET":
        form = EditSubtitleForm(subtitle)
        context["form"] = form
    elif request.method == "POST":
        confirm = request.GET.get("confirm", "").strip()
        if confirm == "true":
            messages.add_message(request, messages.INFO, "Caption was deleted")
            redirect_url = subtitle.media.get_absolute_url()
            subtitle.delete()
            return HttpResponseRedirect(redirect_url)
        form = EditSubtitleForm(subtitle, request.POST)
        subtitle_text = form.data["subtitle"]
        with open(subtitle.subtitle_file.path, "w") as ff:
            ff.write(subtitle_text)

        messages.add_message(request, messages.INFO, "Caption was edited")
        return HttpResponseRedirect(subtitle.media.get_absolute_url())
    return render(request, "cms/edit_subtitle.html", context)


def categories(request):
    """List categories view"""

    context = {}
    return render(request, "cms/categories.html", context)

@login_required
def notifications(request):
    """Personal workspace: notifications page"""
    return render(request, "cms/notifications.html", {})


@login_required
def approvals(request):
    """Personal workspace: approval center"""
    return render(request, "cms/approvals.html", {})


@login_required
def permissions_center(request):
    """Personal workspace: permissions center"""
    return render(request, "cms/permissions.html", {})



@login_required
def clip(request):
    """Online clip editor - WAIC"""
    context = {}
    return render(request, "cms/clip.html", context)


@login_required
def clip_editor(request):
    """OpenReel video editor iframe"""
    path = os.path.join(settings.BASE_DIR, "static", "openreel", "index.html")
    if not os.path.exists(path):
        return HttpResponse(
            "<html><body style='font-family:sans-serif;padding:24px;background:#0f1117;color:#fff;'>"
            "<h2>OpenReel 静态资源未生成</h2>"
            "<p>请先在 <code>frontend-tools/openreel-editor</code> 中安装依赖并构建到 <code>static/openreel/</code>。</p>"
            "</body></html>",
            status=503,
        )

    with open(path, encoding="utf-8") as ff:
        html = ff.read()

    host_config_script = """
<script>
window.OPENREEL_HOST_CONFIG = {
    parentSource: 'mediacms-clip',
    childSource: 'openreel-bridge',
    initialHash: '#/editor'
};
</script>
"""

    if "<head>" in html and "OPENREEL_HOST_CONFIG" not in html:
        html = html.replace("<head>", f"<head>{host_config_script}", 1)

    return HttpResponse(html)


def contact(request):
    """Contact view"""

    context = {}
    if request.method == "GET":
        form = ContactForm(request.user)
        context["form"] = form

    else:
        form = ContactForm(request.user, request.POST)
        if form.is_valid():
            if request.user.is_authenticated:
                from_email = request.user.email
                name = request.user.name
            else:
                from_email = request.POST.get("from_email")
                name = request.POST.get("name")
            message = request.POST.get("message")

            title = f"[{settings.PORTAL_NAME}] - Contact form message received"

            msg = """
You have received a message through the contact form\n
Sender name: %s
Sender email: %s\n
\n %s
""" % (
                name,
                from_email,
                message,
            )
            email = EmailMessage(
                title,
                msg,
                settings.DEFAULT_FROM_EMAIL,
                settings.ADMIN_EMAIL_LIST,
                reply_to=[from_email],
            )
            email.send(fail_silently=True)
            success_msg = "Message was sent! Thanks for contacting"
            context["success_msg"] = success_msg

    return render(request, "cms/contact.html", context)


def history(request):
    """Show personal history view"""

    context = {}
    return render(request, "cms/history.html", context)


_TIMESTAMP_RE = re.compile(r'^(?:(\d+):)?([0-5]?\d):([0-5]?\d)(?:\.(\d{1,3}))?$')


def _timestamp_to_seconds(value):
    """Parse 'HH:MM:SS.mmm', 'MM:SS.mmm', etc., or a numeric value, into float seconds.

    Returns None if the value can't be parsed.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = _TIMESTAMP_RE.match(value.strip())
    if not match:
        return None
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis_str = match.group(4) or '0'
    millis = int(millis_str.ljust(3, '0'))
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


@csrf_exempt
@login_required
def video_chapters(request, friendly_token):
    if not request.method == "POST":
        return HttpResponseRedirect("/")

    media = Media.objects.filter(friendly_token=friendly_token).first()

    if not media:
        return HttpResponseRedirect("/")

    if not (is_mediacms_editor(request.user) or request.user.has_contributor_access_to_media(media)):
        return HttpResponseRedirect("/")

    try:
        request_data = json.loads(request.body)
        data = request_data.get("chapters")
        if data is None:
            return JsonResponse({'success': False, 'error': 'Request must contain "chapters" array'}, status=400)
        if not isinstance(data, list):
            return JsonResponse({'success': False, 'error': '"chapters" must be an array'}, status=400)
        if len(data) > 200:
            return JsonResponse({'success': False, 'error': 'Too many chapters (max 200)'}, status=400)

        chapters = []
        for chapter_data in data:
            if not isinstance(chapter_data, dict):
                continue
            raw_start = chapter_data.get('startTime')
            raw_end = chapter_data.get('endTime')
            chapter_title = chapter_data.get('chapterTitle')

            start_seconds = _timestamp_to_seconds(raw_start)
            end_seconds = _timestamp_to_seconds(raw_end)
            if start_seconds is None or end_seconds is None:
                continue
            if start_seconds < 0 or end_seconds < 0 or start_seconds >= end_seconds:
                continue

            if not isinstance(chapter_title, str) or not chapter_title.strip():
                continue
            chapter_title = strip_tags(chapter_title).strip()[:500]
            if not chapter_title:
                continue

            chapters.append(
                {
                    'startTime': raw_start if isinstance(raw_start, str) else start_seconds,
                    'endTime': raw_end if isinstance(raw_end, str) else end_seconds,
                    'chapterTitle': chapter_title,
                }
            )
    except Exception as e:  # noqa
        return JsonResponse({'success': False, 'error': 'Request data must be a list of video chapters with startTime, endTime, chapterTitle'}, status=400)

    ret = handle_video_chapters(media, chapters)

    return JsonResponse(ret, safe=False)


@login_required
def edit_media(request):
    """Edit a media view"""

    friendly_token = request.GET.get("m", "").strip()
    if not friendly_token:
        return HttpResponseRedirect("/")
    media = Media.objects.filter(friendly_token=friendly_token).first()

    if not media:
        return HttpResponseRedirect("/")

    if not (request.user.has_contributor_access_to_media(media) or is_mediacms_editor(request.user)):
        return HttpResponseRedirect("/")

    if not is_media_allowed_type(media):
        return HttpResponseRedirect(media.get_absolute_url())

    if request.method == "POST":
        form = MediaMetadataForm(request.user, request.POST, request.FILES, instance=media)
        if form.is_valid():
            media = form.save()
            for tag in media.tags.all():
                media.tags.remove(tag)
            if form.cleaned_data.get("new_tags"):
                for tag in form.cleaned_data.get("new_tags").split(","):
                    tag = get_alphanumeric_and_spaces(tag)
                    tag = tag[:100]
                    if tag:
                        try:
                            tag = Tag.objects.get(title=tag)
                        except Tag.DoesNotExist:
                            tag = Tag.objects.create(title=tag, user=request.user)
                        if tag not in media.tags.all():
                            media.tags.add(tag)
            messages.add_message(request, messages.INFO, translate_string(request.LANGUAGE_CODE, "Media was edited"))
            return HttpResponseRedirect(media.get_absolute_url())
    else:
        form = MediaMetadataForm(request.user, instance=media)
    return render(
        request,
        "cms/edit_media.html",
        {"form": form, "media_object": media, "add_subtitle_url": media.add_subtitle_url},
    )


@login_required
def publish_media(request):
    """Publish media"""

    friendly_token = request.GET.get("m", "").strip()
    if not friendly_token:
        return HttpResponseRedirect("/")
    media = Media.objects.filter(friendly_token=friendly_token).first()

    if not media:
        return HttpResponseRedirect("/")

    if not (request.user.has_contributor_access_to_media(media) or is_mediacms_editor(request.user)):
        return HttpResponseRedirect("/")

    if not (request.user.has_owner_access_to_media(media) or is_mediacms_editor(request.user)):
        messages.add_message(request, messages.INFO, translate_string(request.LANGUAGE_CODE, f"Permission to publish is not grated by the owner: {media.user.name}"))
        return HttpResponseRedirect(media.get_absolute_url())

    if request.method == "POST":
        form = MediaPublishForm(request.user, request.POST, request.FILES, instance=media, request=request)
        if form.is_valid():
            media = form.save()
            messages.add_message(request, messages.INFO, translate_string(request.LANGUAGE_CODE, "Media was edited"))
            return HttpResponseRedirect(media.get_absolute_url())
    else:
        form = MediaPublishForm(request.user, instance=media, request=request)

    return render(
        request,
        "cms/publish_media.html",
        {"form": form, "media_object": media, "add_subtitle_url": media.add_subtitle_url},
    )


@login_required
def replace_media(request):
    """Replace media file"""

    if not getattr(settings, 'ALLOW_MEDIA_REPLACEMENT', False):
        return HttpResponseRedirect("/")

    friendly_token = request.GET.get("m", "").strip()
    if not friendly_token:
        return HttpResponseRedirect("/")
    media = Media.objects.filter(friendly_token=friendly_token).first()

    if not media:
        return HttpResponseRedirect("/")

    if not (request.user.has_contributor_access_to_media(media) or is_mediacms_editor(request.user)):
        return HttpResponseRedirect("/")

    if not is_media_allowed_type(media):
        return HttpResponseRedirect(media.get_absolute_url())

    if request.method == "POST":
        form = ReplaceMediaForm(media, request.POST, request.FILES)
        if form.is_valid():
            new_media_file = form.cleaned_data.get("new_media_file")

            media.encodings.all().delete()

            if media.thumbnail:
                helpers.rm_file(media.thumbnail.path)
                media.thumbnail = None
            if media.poster:
                helpers.rm_file(media.poster.path)
                media.poster = None
            if media.uploaded_thumbnail:
                helpers.rm_file(media.uploaded_thumbnail.path)
                media.uploaded_thumbnail = None
            if media.uploaded_poster:
                helpers.rm_file(media.uploaded_poster.path)
                media.uploaded_poster = None
            if media.sprites:
                helpers.rm_file(media.sprites.path)
                media.sprites = None
            if media.preview_file_path:
                helpers.rm_file(media.preview_file_path)
                media.preview_file_path = ""

            if media.hls_file:
                hls_dir = os.path.dirname(media.hls_file)
                helpers.rm_dir(hls_dir)
                media.hls_file = ""

            media.media_file = new_media_file

            media.listable = False
            media.state = helpers.get_default_state(request.user)
            media.save()

            messages.add_message(request, messages.INFO, translate_string(request.LANGUAGE_CODE, "Media file was replaced successfully"))
            return HttpResponseRedirect(media.get_absolute_url())
    else:
        form = ReplaceMediaForm(media)

    return render(
        request,
        "cms/replace_media.html",
        {"form": form, "media_object": media, "add_subtitle_url": media.add_subtitle_url},
    )


@login_required
def edit_chapters(request):
    """Edit chapters"""
    friendly_token = request.GET.get("m", "").strip()
    if not friendly_token:
        return HttpResponseRedirect("/")
    media = Media.objects.filter(friendly_token=friendly_token).first()

    if not media:
        return HttpResponseRedirect("/")

    if not (is_mediacms_editor(request.user) or request.user.has_contributor_access_to_media(media)):
        return HttpResponseRedirect("/")

    _html_escapes = str.maketrans({'<': r'\u003C', '>': r'\u003E', '&': r'\u0026'})
    chapters_json = mark_safe(json.dumps(media.chapter_data).translate(_html_escapes))
    return render(
        request,
        "cms/edit_chapters.html",
        {
            "media_object": media,
            "add_subtitle_url": media.add_subtitle_url,
            "media_file_path": helpers.url_from_path(media.media_file.path),
            "media_id": media.friendly_token,
            "chapters": chapters_json,
        },
    )


@csrf_exempt
@login_required
def trim_video(request, friendly_token):
    if not settings.ALLOW_VIDEO_TRIMMER:
        return JsonResponse({"success": False, "error": "Video trimming is not allowed"}, status=400)

    if not request.method == "POST":
        return HttpResponseRedirect("/")

    media = Media.objects.filter(friendly_token=friendly_token).first()

    if not media:
        return HttpResponseRedirect("/")

    if not (is_mediacms_editor(request.user) or request.user.has_contributor_access_to_media(media)):
        return HttpResponseRedirect("/")

    existing_requests = VideoTrimRequest.objects.filter(media=media, status__in=["initial", "running"]).exists()

    if existing_requests:
        return JsonResponse({"success": False, "error": "A trim request is already in progress for this video"}, status=400)

    try:
        data = json.loads(request.body)
        video_trim_request = create_video_trim_request(media, data)
        video_trim_task.delay(video_trim_request.id)
        ret = {"success": True, "request_id": video_trim_request.id}
        return JsonResponse(ret, safe=False, status=200)
    except Exception as e:  # noqa
        ret = {"success": False, "error": "Incorrect request data"}
        return JsonResponse(ret, safe=False, status=400)


@login_required
def edit_video(request):
    """Edit video"""

    friendly_token = request.GET.get("m", "").strip()
    if not friendly_token:
        return HttpResponseRedirect("/")
    media = Media.objects.filter(friendly_token=friendly_token).first()

    if not media:
        return HttpResponseRedirect("/")

    if not (is_mediacms_editor(request.user) or request.user.has_contributor_access_to_media(media)):
        return HttpResponseRedirect("/")

    if media.media_type not in ["video", "audio"]:
        messages.add_message(request, messages.INFO, "Media is not video or audio")
        return HttpResponseRedirect(media.get_absolute_url())

    if not settings.ALLOW_VIDEO_TRIMMER:
        messages.add_message(request, messages.INFO, "Video Trimmer is not enabled")
        return HttpResponseRedirect(media.get_absolute_url())

    # Check if there's a running trim request
    running_trim_request = VideoTrimRequest.objects.filter(media=media, status__in=["initial", "running"]).exists()

    if running_trim_request:
        messages.add_message(request, messages.INFO, "Video trim request is already running")
        return HttpResponseRedirect(media.get_absolute_url())

    media_file_path = media.trim_video_url

    if not media_file_path:
        messages.add_message(request, messages.INFO, "Media processing has not finished yet")
        return HttpResponseRedirect(media.get_absolute_url())

    if media.encoding_status in ["pending", "running"]:
        video_msg = "Media encoding hasn't finished yet. Attempting to show the original video file"
        messages.add_message(request, messages.INFO, video_msg)

    return render(
        request,
        "cms/edit_video.html",
        {"media_object": media, "add_subtitle_url": media.add_subtitle_url, "media_file_path": media_file_path},
    )


def embed_media(request):
    """Embed media view"""

    friendly_token = request.GET.get("m", "").strip()
    if not friendly_token:
        return HttpResponseRedirect("/")

    media = Media.objects.values("title").filter(friendly_token=friendly_token).first()

    if not media:
        return HttpResponse('This media no longer exists', status=404, content_type='text/plain; charset=utf-8')

    context = {}
    context["media"] = friendly_token
    return render(request, "cms/embed.html", context)


def featured_media(request):
    """List featured media view"""

    context = {}
    return render(request, "cms/featured-media.html", context)


def index(request):
    """Index view"""
    from datetime import date
    from ..models import Media

    # 分类统计 — 取不包含子分类标识的顶级分类
    categories = []
    for cat in waic_fixed_category_queryset():
        # 跳过子分类（标题含 " > "）
        count = Media.objects.filter(category=cat, state='public').count()
        categories.append({
            'title': cat.title,
            'count': count,
        })

    # 首页统计
    total_media = Media.objects.filter(state='public').count()
    today_media = Media.objects.filter(
        state='public', add_date__date=date.today()
    ).count()

    context = {
        'categories': categories,
        'total_media': total_media,
        'today_media': today_media,
        'category_count': len(categories),
    }
    return render(request, "cms/index.html", context)


def latest_media(request):
    """List latest media view"""

    context = {}
    return render(request, "cms/latest-media.html", context)


def liked_media(request):
    """List user's liked media view"""

    context = {}
    return render(request, "cms/liked_media.html", context)


@login_required
def manage_users(request):
    """List users management view"""

    if not is_mediacms_editor(request.user):
        return HttpResponseRedirect("/")

    context = {}
    return render(request, "cms/manage_users.html", context)


@login_required
def manage_media(request):
    """List media management view"""
    if not is_mediacms_editor(request.user):
        return HttpResponseRedirect("/")

    categories = [category["title"] for category in waic_fixed_category_options()]
    context = {'categories': categories}
    return render(request, "cms/manage_media.html", context)


@login_required
def manage_comments(request):
    """List comments management view"""
    if not is_mediacms_editor(request.user):
        return HttpResponseRedirect("/")

    context = {}
    return render(request, "cms/manage_comments.html", context)


def members(request):
    """List members view"""

    if settings.CAN_SEE_MEMBERS_PAGE == "editors" and not is_mediacms_editor(request.user):
        return HttpResponseRedirect("/")

    if settings.CAN_SEE_MEMBERS_PAGE == "admins" and not request.user.is_superuser:
        return HttpResponseRedirect("/")

    context = {}
    return render(request, "cms/members.html", context)


def recommended_media(request):
    """List recommended media view"""

    context = {}
    return render(request, "cms/recommended-media.html", context)


def search(request):
    """Search view"""

    context = {}
    RSS_URL = f"/rss{request.environ.get('REQUEST_URI')}"
    context["RSS_URL"] = RSS_URL
    return render(request, "cms/search.html", context)


def sitemap(request):
    """Sitemap"""

    context = {}
    context["media"] = list(Media.objects.filter(listable=True).order_by("-add_date"))
    context["playlists"] = list(Playlist.objects.filter().order_by("-add_date"))
    context["users"] = list(User.objects.filter())
    return render(request, "sitemap.xml", context, content_type="application/xml")


def tags(request):
    """List tags view"""

    context = {}
    return render(request, "cms/tags.html", context)


def tos(request):
    """Terms of service view"""

    context = {}
    return render(request, "cms/tos.html", context)


@login_required
def upload_media(request):
    """Upload media view"""

    from allauth.account.forms import LoginForm

    form = LoginForm()
    context = {}
    context["form"] = form
    context["can_add"] = user_allowed_to_upload(request)
    can_upload_exp = settings.CANNOT_ADD_MEDIA_MESSAGE
    context["can_upload_exp"] = can_upload_exp
    context["categories"] = waic_fixed_category_options()

    return render(request, "cms/add-media.html", context)


def view_media(request):
    """View media view"""

    friendly_token = request.GET.get("m", "").strip()
    context = {}
    media = Media.objects.filter(friendly_token=friendly_token).first()
    if not media:
        context["media"] = None
        return render(request, "cms/media.html", context)

    user_or_session = get_user_or_session(request)
    save_user_action.delay(user_or_session, friendly_token=friendly_token, action="watch")
    context = {}
    context["media"] = friendly_token
    context["media_id"] = media.id
    context["media_object"] = media

    context["CAN_DELETE_MEDIA"] = False
    context["CAN_EDIT_MEDIA"] = False
    context["CAN_DELETE_COMMENTS"] = False

    if request.user.is_authenticated:
        if request.user.has_contributor_access_to_media(media) or is_mediacms_editor(request.user):
            context["CAN_EDIT_MEDIA"] = True
            context["CAN_DELETE_COMMENTS"] = True

        if request.user == media.user or is_mediacms_editor(request.user):
            context["CAN_DELETE_MEDIA"] = True

    # in case media is video and is processing (eg the case a video was just uploaded)
    # attempt to show it (rather than showing a blank video player)
    if media.media_type == 'video':
        video_msg = None
        if media.encoding_status == "pending":
            video_msg = "Media encoding hasn't started yet. Attempting to show the original video file"
        if media.encoding_status == "running":
            video_msg = "Media encoding is under processing. Attempting to show the original video file"
        if video_msg and media.user == request.user:
            messages.add_message(request, messages.INFO, video_msg)

    context["is_media_allowed_type"] = is_media_allowed_type(media)
    return render(request, "cms/media.html", context)


def media_inline_preview(request, friendly_token):
    """Render a safe inline HTML preview for non-video media."""

    media = Media.objects.select_related("user").filter(friendly_token=friendly_token).first()
    if not media:
        return HttpResponse("Media not found", status=404)

    if media.state == "private":
        allowed = False
        if request.user.is_authenticated:
            allowed = (
                request.user == media.user
                or request.user.has_member_access_to_media(media)
                or is_mediacms_editor(request.user)
            )
        if not allowed:
            return HttpResponse("Forbidden", status=403)

    if not media.media_file:
        return HttpResponse(_waic_preview_shell(media.title, '<div class="empty">没有可预览的文件。</div>'))

    path = media.media_file.path
    ext = os.path.splitext(path)[1].lower()
    pdf_conversion_error = None
    if request.GET.get("format") == "pdf" and ext in WAIC_OFFICE_PDF_EXTENSIONS:
        try:
            pdf_path = _waic_office_pdf_path(media, path)
            response = FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{media.friendly_token}.pdf"'
            return response
        except Exception as exc:
            pdf_conversion_error = str(exc)

    try:
        if ext in (".docx",):
            body = _waic_docx_preview(path)
            kind = "DOCX_PREVIEW"
        elif ext in (".pptx",):
            body = _waic_pptx_preview(path)
            kind = "PPTX_PREVIEW"
        elif ext in (".xlsx", ".xlsm"):
            body = _waic_xlsx_preview(path)
            kind = "XLSX_PREVIEW"
        elif ext in (".txt", ".md", ".csv", ".json", ".xml", ".log", ".rst"):
            body = _waic_text_preview(path)
            kind = "TEXT_PREVIEW"
        else:
            body = '<div class="empty">此文件类型暂不支持页面内解析预览，请下载后查看。</div>'
            kind = "FILE_PREVIEW"
    except Exception as exc:
        body = f'<div class="empty">预览生成失败：{escape(str(exc))}</div>'
        kind = "PREVIEW_ERROR"

    if pdf_conversion_error:
        body = (
            '<div class="empty">PDF 预览暂不可用，已切换为文本降级预览。'
            f"<br>{escape(pdf_conversion_error)}</div>"
            + body
        )

    return HttpResponse(_waic_preview_shell(media.title, body, kind=kind), content_type="text/html; charset=utf-8")


def view_playlist(request, friendly_token):
    """View playlist view"""

    try:
        playlist = Playlist.objects.get(friendly_token=friendly_token)
    except BaseException:
        playlist = None

    context = {}
    context["playlist"] = playlist
    return render(request, "cms/playlist.html", context)
