# WAIC 素材平台 — 技术架构全景

> 2026-05-24 分析

## 组件清单

| 层 | 技术 | 版本 | 角色 |
|---|---|---|---|
| 后端框架 | Django | 5.2.6 | ORM / REST / Admin / 模板 |
| API | Django REST Framework | 3.16 | REST API 端点 |
| 前端 | React | 19 | SPA (多入口页面) |
| 前端类型 | TypeScript | - | 编译时类型 |
| 构建工具 | Webpack (mediacms-scripts) | - | 自定义构建链 |
| 状态管理 | Flux | - | 前端状态 |
| 样式 | SCSS + PostCSS + Autoprefixer | - | 编译到 CSS |
| 模板引擎 | EJS | - | 前端模板 |
| 数据库 | PostgreSQL | psycopg 3.2 | 主存储 |
| 缓存/队列 | Redis | 6379/1 | Cache + Celery Broker |
| 异步任务 | Celery | 5.4 | 转码/字幕/AI分析 |
| WSGI | Gunicorn | 23 | 生产服务器 |
| 视频处理 | FFmpeg | - | 转码/降噪 |
| 语音识别 | openai-whisper | medium | 本地字幕生成 |
| AI分析 | DashScope (Qwen) | - | 图片/文档分析+嵌入 |
| 认证 | django-allauth + python3-saml | - | 本地+SAML SSO |
| Admin | django-jazzmin | 3.0 | 后台皮肤 |
| 富文本 | django-tinymce | 4.1 | 内容编辑 |
| 文件上传 | FineUploader (CDN) | 5.13 | 分片上传 |
| 错误监控 | Sentry | - | 生产错误追踪 |
| API文档 | drf-yasg | - | OpenAPI/Swagger |

## 架构判断：标准单体，非缝合怪

MediaCMS v8 本身就是成熟的 Django + React 单体应用。WAIC 加的功能（审批/水印/Word搜索/权限申请/分享弹窗/通知）全是 Django 应用层扩展，零新依赖。

## 当前部署方式（开发模式）

```
PostgreSQL ────┐
Redis ─────────┼──→ Django runserver :8005 ──→ 用户
Celery Worker ─┘   (--noreload, WSL /mnt/h/)
Celery Beat ───┘
```

5 个进程全手动管理，无 Docker/编排。

## 生产化打包方案

```
docker-compose.yml
├── postgres      (postgres:16-alpine)
├── redis         (redis:7-alpine)
├── web           (Django + Gunicorn, 同镜像)
├── celery_worker (同镜像，CMD: celery worker)
└── celery_beat   (同镜像，CMD: celery beat)
```

**缺失**：项目无 Dockerfile、无 docker-compose.yml、无 CI/CD。

## 进程启动命令（当前）

```bash
# Django
PYTHONUNBUFFERED=1 venv/bin/python manage.py runserver 0.0.0.0:8005 --noreload

# Celery Worker
DJANGO_SETTINGS_MODULE=cms.settings celery -A cms worker -Q long_tasks,short_tasks -l INFO --concurrency=2

# Celery Beat
DJANGO_SETTINGS_MODULE=cms.settings celery -A cms beat -l INFO
```

## 关键配置文件

| 文件 | 用途 |
|---|---|
| `requirements.txt` | Python 依赖 (27 packages) |
| `frontend/package.json` | Node 依赖 (mediacms-scripts + webpack生态) |
| `cms/settings.py` | Django 主配置 (668行) |
| `cms/local_settings.py` | 本地覆盖 (最后加载) |
| `cms/wsgi.py` | Gunicorn 入口 |
