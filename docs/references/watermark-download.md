# 水印下载 — 实现细节 (2026-05-21)

## 设计决策（坚哥确认）

- ❌ 在线浏览无水印
- ✅ 下载时动态叠加，不预存水印版本
- ✅ 图片/PDF 加水印，视频/音频跳过（视频FFmpeg重编码太慢）
- ✅ 白色半透明 style，不要黑底矩形框
- ✅ WAIC logo + 日期，PIL white-alpha 提取

## 架构

```
前端下载按钮 → href?dl=1 → Django URL路由拦截 → watermark_download视图
                                       ↕
                         ?dl=1: 加水印返回
                         no dl: django.views.static.serve 原样返回
```

## 关键文件

| 文件 | 作用 |
|------|------|
| `files/views/watermark.py` | PIL图片水印 + PyMuPDF PDF水印 |
| `files/urls.py` | 路由 `^media/(jpg\|jpeg\|png\|gif\|webp\|bmp\|tiff\|tif\|pdf)$` |
| `OtherMediaDownloadLink.jsx` | href 拼接 `?dl=1` |
| `MediaMoreOptionsIcon.jsx` | downloadLink 拼接 `?dl=1` |

## 水印路由陷阱 ⚠️

`MEDIA_URL = "/media/"` 是URL前缀，`MEDIA_ROOT = "media_files/"` 是文件系统目录。两者不同！

```python
# ❌ 错误 — 永远匹配不到
re_path(r'^media_files/...', ...)

# ✅ 正确
re_path(r'^media/...', ...)
```

路由必须放在 `range_serve`（视频serve）和 `static()`（兜底）之前。

## 水印样式实现

### 图片 (PIL)
```python
# 1. 读取 WAIC logo → 提取alpha通道
logo = Image.open('waic-logo-original.png').convert('RGBA')
r, g, b, a = logo.split()

# 2. 纯白fill + alpha shape
white_logo = Image.new('RGBA', logo.size, (255, 255, 255, 0))
white_logo.putalpha(a)

# 3. 降低opacity → max 140
data = [(255, 255, 255, min(p[3], 140)) for p in white_logo.getdata()]

# 4. 叠加到图片
overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
overlay.paste(white_logo, (logo_x, y), white_logo)
draw.text((text_x, text_y), "WAIC · 2026-05-21", fill=(255,255,255,160))
img = Image.alpha_composite(img.convert('RGBA'), overlay)
```

### PDF (PyMuPDF)
```python
page.insert_text(point, "WAIC · 2026-05-21", fontname='helv', fontsize=12, color=(1,1,1))
shape.draw_rect(...)  # 半透明背景
```

## 测试验证

```bash
# 原图（无水印）
curl -s -o /dev/null -w "%{size_download}" http://localhost:8005/media/original/xxx.jpg
# → 825

# 水印下载
curl -s -o /dev/null -w "%{size_download}" "http://localhost:8005/media/original/xxx.jpg?dl=1"
# → 2475  （明显变大 = 水印已应用）
```

## 依赖

```bash
pip install Pillow PyMuPDF  # 都在 venv 中已安装
```
