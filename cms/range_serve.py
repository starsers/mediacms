"""
Range-request aware media serving for video seeking support.
Django's dev server doesn't handle HTTP Range requests,
which breaks video seeking. This view adds proper 206 Partial Content.
"""
import os
import re
from django.http import HttpResponse, HttpResponseNotModified
from django.conf import settings


def range_serve(request, path):
    """Serve a media file with Range header support for video seeking."""
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    
    # Security: prevent directory traversal
    full_path = os.path.normpath(full_path)
    if not full_path.startswith(os.path.normpath(settings.MEDIA_ROOT)):
        return HttpResponse(status=403)
    
    if not os.path.exists(full_path):
        return HttpResponse(status=404)
    
    file_size = os.path.getsize(full_path)
    content_type = _guess_content_type(full_path)
    
    range_header = request.META.get('HTTP_RANGE', '')
    if not range_header:
        # No Range header — serve full file
        with open(full_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
        response['Content-Length'] = file_size
        response['Accept-Ranges'] = 'bytes'
        return response
    
    # Parse Range: bytes=start-end
    match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    if not match:
        return HttpResponse(status=416)  # Range Not Satisfiable
    
    start = int(match.group(1))
    end_str = match.group(2)
    end = int(end_str) if end_str else file_size - 1
    
    if start >= file_size:
        return HttpResponse(status=416)
    
    end = min(end, file_size - 1)
    length = end - start + 1
    
    with open(full_path, 'rb') as f:
        f.seek(start)
        data = f.read(length)
    
    response = HttpResponse(data, status=206, content_type=content_type)
    response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    response['Content-Length'] = length
    response['Accept-Ranges'] = 'bytes'
    return response


def _guess_content_type(path):
    import mimetypes
    ct, _ = mimetypes.guess_type(path)
    return ct or 'application/octet-stream'
