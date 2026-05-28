# Django Dev Server — 视频 Seek 修复（Range 请求支持）

## 问题
Django `runserver` 不处理 HTTP `Range: bytes=` 头，导致 `<video>` 元素无法 seek（`currentTime = X` 设置后实际值仍为 0）。所有视频时间戳跳转功能失效。

## 根因
浏览器对 `<video>` 的 seek 操作会发送带 `Range: bytes=START-` 头的 HTTP 请求，期望服务器返回 `206 Partial Content`。Django dev server 的 `django.views.static.serve` 不支持此头 → 返回完整文件或 200 → 浏览器无法定位。

## 修复：`range_serve` 视图

### 文件：`cms/range_serve.py`
```python
import os, re, mimetypes
from django.http import HttpResponse
from django.conf import settings

def range_serve(request, path):
    """Serve a media file with Range header support for video seeking."""
    full_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, path))
    if not full_path.startswith(os.path.normpath(settings.MEDIA_ROOT)):
        return HttpResponse(status=403)
    if not os.path.exists(full_path):
        return HttpResponse(status=404)

    file_size = os.path.getsize(full_path)
    ct, _ = mimetypes.guess_type(full_path)
    content_type = ct or 'application/octet-stream'

    range_header = request.META.get('HTTP_RANGE', '')
    if not range_header:
        with open(full_path, 'rb') as f:
            resp = HttpResponse(f.read(), content_type=content_type)
        resp['Content-Length'] = file_size
        resp['Accept-Ranges'] = 'bytes'
        return resp

    match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    if not match:
        return HttpResponse(status=416)

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

    resp = HttpResponse(data, status=206, content_type=content_type)
    resp['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    resp['Content-Length'] = length
    resp['Accept-Ranges'] = 'bytes'
    return resp
```

### URL 注册：`files/urls.py`
```python
from cms.range_serve import range_serve

urlpatterns = [
    # ... 其他 URL ...
    re_path(r'^media/(?P<path>.+\.(mp4|webm|ogg|mov|avi|mkv|flv|wmv|m4v|mp3|wav|flac|aac|wma))$',
            range_serve, name='range_media'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**关键**：`range_serve` 必须在 `static()` 之前注册，这样媒体文件请求走 Range-aware 视图，其他文件 fallback 到 Django 默认 static serve。

## 验证
```bash
# 请求 Range
curl -s -o /dev/null -w "%{http_code}" -H "Range: bytes=0-1024" \
  http://localhost:8005/media/original/user/admin/test.mp4
# 期望: 206
```
