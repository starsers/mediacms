# MediaCMS Remix — 内部视频平台改造指南

## 环境
- **WSL2 Ubuntu** 是唯一运行环境，不在 Windows 上执行代码
- Python 3.11 虚拟环境：`source venv/bin/activate`
- PostgreSQL 18.3：库 `mediacms`，用户 `mediacms`，密码 `mediacms`，主机 `127.0.0.1`
- Django 5.2.6，启动：`python manage.py runserver 0.0.0.0:8005`
- 所有命令在项目根目录 `/mnt/h/media-cms-v7/` 执行
- 不要碰 Windows 路径，不要用 Docker。Bento4/FFmpeg 路径见 `cms/local_settings.py`

## 最高优先级安全规则
- 永远不修改 `files/` 核心媒体处理逻辑（上传/转码/编码/存储路径）
- 永远不修改 `users/` 用户认证核心（登录/注册/密码）
- 删除任何模块前，先在 `cms/settings.py` 和 `cms/urls.py` 中移除其引用，再删文件
- 每次删除操作后立即运行 `python manage.py check --deploy` 确认零错误
- 修改前端后运行 `python manage.py collectstatic --noinput`

## 需要删除的模块（教育/SSO 相关，本项目无用）
| 模块 | 目录 | 原因 |
|------|------|------|
| LTI 1.3 | `lti/` | 教学平台对接，完全用不着 |
| SAML 认证 | `saml_auth/` | 单点登录，无 SAML IdP |
| 身份提供商 | `identity_providers/` | SSO 配置，跟 SAML 配套 |
| LMS 插件 | `lms-plugins/` | Moodle 插件 |
| Docker 部署 | `deploy/`、`docker-compose/` | 裸机运行，不用容器 |

删除步骤：先在 `cms/settings.py` 中注释/删除对应 INSTALLED_APPS → 在 `cms/urls.py` 中删除路由 → 删除目录 → `check` 验证

## 需要加强的核心功能
| 功能 | 目录 | 目标 |
|------|------|------|
| RBAC 权限 | `rbac/` | 确保账号级媒体访问隔离，媒体给不同账号看到不同内容 |
| 字幕系统 | `files/` 中的字幕相关 | 保留 WebVTT 时间轴结构，准备对接华为云 ASR 替换 Whisper |
| 推荐板块 | `files/views/` + 前端 | 新增「热门推荐」「今日推荐」API + 首页模块 |
| 前端改头换面 | `frontend/` + `templates/` | 换 Logo/名字/配色/首页布局，看不出 MediaCMS 痕迹 |

## 不要做的事情
- 不要碰 `files/models/` 核心数据模型（Media/EncodeProfile/Subtitle）
- 不要碰迁移文件（`*/migrations/` 下已有记录）
- 不要创建新的 Django app，在现有 `files/` 内扩展
- 不要引入新的 Python 依赖，除非绝对必要且在 `requirements.txt` 中声明
- 不要修改 `cms/settings.py` 中的 DATABASES/CACHES/CELERY 配置块
- 不要改 `frontend/` 的 React 源码（已有编译好的 `static/`，直接改静态文件更快）
- 不要删 `tests/` 目录，改界面后测试会爆红但不影响运行

## 文件路径速查
- 核心配置：`cms/settings.py`（默认）、`cms/local_settings.py`（本地覆盖）
- URL 路由：`cms/urls.py`
- 媒体处理：`files/views/`、`files/models/`、`files/tasks.py`
- 用户管理：`users/views.py`、`users/models.py`
- 前端模板：`templates/`（Django 模板）、`frontend/config/templates/static/`（静态页面）
- 静态资源：`static/`（编译后 JS/CSS/图片，改这里）
- 管理后台定制：`admin_customizations/`

## 改界面快速入口
1. 站点名称/Logo → `cms/local_settings.py` 加 `PORTAL_NAME`、改 `static/` 里的 logo 文件
2. 首页布局 → `templates/` 和 `frontend/config/templates/static/`
3. 配色主题 → `cms/local_settings.py` 设 `DEFAULT_THEME`，覆盖 `static/` 中的 CSS
4. 页脚/版权 → `templates/` 中搜索 "MediaCMS" 全文替换
