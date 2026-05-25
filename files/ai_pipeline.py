"""
DashScope AI Pipeline for MediaCMS v8.

Provides:
- analyze_audio(media) → Speech-to-text via DashScope Paraformer
- analyze_video(media) → Extract audio from video, then transcribe

DashScope Paraformer docs: https://help.aliyun.com/document_detail/2712534.html
"""

import json
import os
import tempfile

from django.conf import settings
from django.core.files import File as DjangoFile

from .models import Subtitle, Language


def _get_api_key():
    return getattr(settings, 'DASHSCOPE_API_KEY', os.environ.get('DASHSCOPE_API_KEY', ''))


def _extract_audio(media):
    """Extract audio as low-bitrate mono MP3 (fits DashScope 6MB limit), return temp path."""
    import subprocess

    tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False, dir=getattr(settings, 'TEMP_DIRECTORY', '/tmp'))
    tmp.close()
    mp3_path = tmp.name

    cmd = [
        'ffmpeg', '-y',
        '-i', media.media_file.path,
        '-vn',
        '-acodec', 'libmp3lame',
        '-ar', '16000',
        '-ac', '1',
        '-b:a', '16k',
        mp3_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr[:500]}")

    return mp3_path


def _dashscope_transcribe(audio_path: str, media=None) -> list:
    """
    Transcribe audio via DashScope qwen3-asr-flash (multimodal API).
    Splits long audio into 4.5-min chunks, transcribes each via base64 data URL.
    Returns: [{start_ms, end_ms, text}, ...]
    """
    import http.client
    import time as _time
    import base64

    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY not configured")

    import subprocess as _sp

    # Get audio duration in seconds
    probe = _sp.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
        capture_output=True, text=True, timeout=30)
    total_sec = float(probe.stdout.strip())
    chunk_sec = 270  # 4.5 minutes per chunk (under 5-min limit)
    print(f"  Audio duration: {total_sec:.0f}s, chunking into {chunk_sec}s pieces")

    all_segments = []
    offset_ms = 0

    for start_sec in range(0, int(total_sec), chunk_sec):
        # Extract chunk via ffmpeg
        import tempfile as _tf
        tmp = _tf.NamedTemporaryFile(suffix='.mp3', delete=False,
            dir=getattr(settings, 'TEMP_DIRECTORY', '/tmp'))
        tmp.close()
        _sp.run([
            'ffmpeg', '-y', '-i', audio_path,
            '-ss', str(start_sec), '-t', str(chunk_sec),
            '-vn', '-acodec', 'libmp3lame', '-ar', '16000', '-ac', '1', '-b:a', '16k',
            tmp.name
        ], capture_output=True, timeout=120)

        with open(tmp.name, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        os.unlink(tmp.name)

        data_url = f'data:audio/mpeg;base64,{b64}'
        payload = json.dumps({
            'model': 'qwen3-asr-flash',
            'input': {'messages': [{'role': 'user', 'content': [{'audio': data_url}]}]},
            'parameters': {'result_format': 'message'}
        })

        conn = http.client.HTTPSConnection("dashscope.aliyuncs.com")
        conn.request('POST', '/api/v1/services/aigc/multimodal-generation/generation',
            body=payload,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'})
        resp = conn.getresponse()
        result = json.loads(resp.read().decode('utf-8'))
        conn.close()

        if result.get('code'):
            print(f"  Chunk {start_sec}s failed: {result.get('message','')[:100]}")
            continue

        # Parse result
        text = ''
        for ch in result.get('output', {}).get('choices', []):
            msg = ch.get('message', {})
            content = msg.get('content', '')
            if isinstance(content, list):
                text = ''.join(c.get('text', '') for c in content if isinstance(c, dict))
            elif isinstance(content, str):
                text = content

        if text.strip():
            all_segments.append({
                'start_ms': offset_ms,
                'end_ms': offset_ms + chunk_sec * 1000,
                'text': text.strip(),
            })

        offset_ms += chunk_sec * 1000
        _time.sleep(0.5)  # Rate limit

    if not all_segments:
        raise RuntimeError("No speech segments transcribed — audio may be silent")

    print(f"  Transcribed {len(all_segments)} chunks, {sum(len(s['text']) for s in all_segments)} total chars")
    return all_segments


def _ms_to_vtt(ms):
    h = int(ms // 3600000)
    m = int((ms % 3600000) // 60000)
    s = int((ms % 60000) // 1000)
    x = int(ms % 1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{x:03d}'


def _write_vtt(segments: list) -> str:
    """Write segments to a temp VTT file, return path."""
    lines = ['WEBVTT', '']
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f'{_ms_to_vtt(seg["start_ms"])} --> {_ms_to_vtt(seg["end_ms"])}')
        lines.append(seg['text'])
        lines.append('')

    tmp = tempfile.NamedTemporaryFile(
        suffix='.vtt', mode='w', delete=False, encoding='utf-8',
        dir=getattr(settings, 'TEMP_DIRECTORY', '/tmp'),
    )
    tmp.write('\n'.join(lines))
    tmp.close()
    return tmp.name


def _get_or_create_lang(code='zh'):
    lang, _ = Language.objects.get_or_create(
        code=code,
        defaults={'title': 'Chinese' if code == 'zh' else code},
    )
    return lang


def _get_first_user():
    from users.models import User
    user = User.objects.filter(is_superuser=True).first()
    return user or User.objects.first()


def analyze_audio(media):
    """Transcribe audio → create Subtitle with Chinese VTT."""
    audio_path = None
    vtt_path = None
    try:
        audio_path = _extract_audio(media)
        segments = _dashscope_transcribe(audio_path)
        vtt_path = _write_vtt(segments)

        with open(vtt_path, 'rb') as f:
            lang = _get_or_create_lang('zh')
            user = _get_first_user()
            sub = Subtitle(media=media, language=lang, user=user)
            sub.subtitle_file.save(f'{media.friendly_token}_ai.vtt', DjangoFile(f), save=True)

    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        if vtt_path and os.path.exists(vtt_path):
            os.remove(vtt_path)


def analyze_video(media):
    """Extract audio from video and transcribe."""
    analyze_audio(media)
