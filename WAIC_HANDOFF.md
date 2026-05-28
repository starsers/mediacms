# WAIC 素材平台 — 开发交接文档

> 生成日期: 2026-05-27
> 项目路径: H:\media-cms-v7
> 原始项目: MediaCMS v8.0.8 (https://github.com/mediacms-io/mediacms)

---

## 一、项目概述

**WAIC 素材平台**是世界人工智能大会（WAIC）内部使用的媒体素材分享系统。基于开源项目 MediaCMS v8.0.8 二次开发，增加了审批流程、AI 智能分析、权限申请系统、水印下载、中文搜索优化等功能。

- 管理员账号: `admin` / `admin123`
- 本地访问: http://localhost:8005
- 管理后台: http://localhost:8005/admin
- 数据库: PostgreSQL `mediacms_v7`
- Git: `git@github.com:mediacms-io/mediacms.git` (main 分支)

---

## 二、技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | **Django 5.2** | REST API (DRF 3.16) + 模板渲染 |
| 前端框架 | **React 17 + Flux** | SPA，Webpack 编译，SCSS 样式 |
| 数据库 | **PostgreSQL** | pgvector 向量搜索，全文检索 |
| 缓存/队列 | **Redis + Celery 5.4** | 异步任务（AI/转码/转录） |
| 媒体处理 | **FFmpeg + Bento4** | 视频转码、HLS 分片 |
| AI 服务 | **DashScope API** + **Whisper** | 视觉识别、语音转录、文本嵌入 |
| 其他 | **FineUploader, VideoJS, PIL, PyMuPDF** | 上传、播放、水印 |

---

## 三、项目目录结构

```
H:\media-cms-v7/
├── cms/                    # Django 核心配置
│   ├── settings.py         #   主配置
│   ├── local_settings.py   # ★ 本地覆盖（品牌/数据库/Logo/主题）
│   ├── urls.py             #   主路由
│   └── range_serve.py      #   视频 Range 请求支持
├── files/                  # ★ 核心 App（媒体处理）
│   ├── models/             #   Media, Category, Tag, Subtitle, 审批模型
│   ├── views/              #   API views, 页面 views, 水印 views
│   ├── tasks.py            #   Celery 异步任务（AI/转录/降噪/嵌入）
│   ├── ai_analysis.py      #   AI 分析主逻辑
│   ├── ai_pipeline.py      #   音视频处理管道
│   ├── methods.py          #   通知系统 notify_users
│   └── frontend_translations/  # 前端翻译键（zh_hans.py / en.py）
├── users/                  # 用户 App（User, Notification, Permission）
├── templates/              # Django 模板
│   ├── cms/                #   页面模板（首页/上传/详情/审批/权限…）
│   ├── config/             #   MediaCMS 配置注入（contents.html 等）
│   └── root.html           #   根模板（CSS/JS 加载顺序）
├── static/                 # ★ 静态文件（编译产物）
│   ├── css/waic-theme.css  #   ★ WAIC 主题 CSS（Stripe/Linear 双模）
│   ├── css/_commons.css    #   Webpack 编译产物（不要手改！）
│   ├── images/             #   Logo、Favicon
│   ├── js/                 #   编译后 React bundle
│   └── jianshen/           #   剪神在线编辑器
├── frontend/               # React 源码
│   ├── src/                #   JSX 组件（97 个）
│   ├── static/css/         #   SCSS 源文件
│   └── config/             #   Webpack 配置
├── venv/                   # Python 虚拟环境（~2GB，不打包）
├── media_files/            # 上传的媒体文件（不打包）
├── static_collected/       # collectstatic 输出（不打包）
├── requirements.txt        # Python 依赖
├── WAIC_HANDOFF.md         # ★ 本文档
├── DESIGN.md               # 设计 Token 定义
├── CLAUDE_TASKS.md         # Claude Code 任务指南
└── AGENTS.md               # Claude Code 当前任务
```

---

## 四、环境搭建

### 4.1 前置依赖

- Python 3.11+
- Node.js 18+
- PostgreSQL (数据库 `mediacms_v7`)
- Redis
- FFmpeg + Bento4（视频转码）
- Git

### 4.2 Python 环境

```bash
cd H:\media-cms-v7
python -m venv venv
venv\Scripts\activate      # Windows
# 或 source venv/bin/activate  # Linux/WSL

pip install -r requirements.txt
pip install openai-whisper  # 本地语音转录（可选）
```

### 4.3 数据库初始化

```bash
# 创建数据库
createdb mediacms_v7 -U mediacms

# 运行迁移
python manage.py migrate

# 创建管理员
python manage.py createsuperuser
```

### 4.4 前端编译

```bash
cd frontend
npm install
npm run dist
cp -r dist/static/* ../static/
```

### 4.5 配置调整

编辑 `cms/local_settings.py`：
- `DATABASES` → 数据库连接信息
- `DASHSCOPE_API_KEY` → 阿里云 DashScope API Key
- `PORTAL_NAME` → 站点名称

---

## 五、运行服务

### 开发模式（最小启动）

```bash
# 1. 确保 PostgreSQL 和 Redis 在运行
# 2. 启动 Django
python manage.py runserver 0.0.0.0:8005 --noreload

# 3. 启动 Celery Worker（可选，AI 分析需要）
celery -A cms worker -Q long_tasks,short_tasks -l INFO --concurrency=2

# 4. 启动 Celery Beat（可选，定时任务）
celery -A cms beat -l INFO
```

### WSL 特别注意

项目在 Windows 挂载盘（H: → /mnt/h/）上，跨文件系统极慢：
- Django 必须加 `--noreload` 跳过文件监控（否则 60s+ 才能启动）
- 改 Python 代码后需手动重启服务器
- 模板改后建议重启（缓存行为不一致）

---

## 六、WAIC 定制功能清单

### 6.1 品牌与视觉
- **双模主题**: Stripe 亮色 + Linear 暗色（`static/css/waic-theme.css`）
- **品牌色**: #1a56db (WAIC 蓝), #1e3a5f (深海军蓝侧边栏)
- **WAIC Logo**: `static/images/waic-logo-original.png`
- **Favicon**: WAIC 蓝标替换 MediaCMS 绿色
- **侧边栏**: 240px，折叠功能，通知铃铛，去掉第三方品牌
- **自定义首页**: Hero + 统计卡片 + 分类导航

### 6.2 审批工作流
- **模型**: `Media.approval_status` (pending/submitted/approved/rejected)
- **API**: 4 个审批端点 (`/api/v1/approval/submit|approve|reject|pending`)
- **通知**: 邮件 + 系统消息双通道
- **配置**: `cms/local_settings.py` 中 `APPROVAL_REVIEWER`

### 6.3 权限系统
- **三级角色**: admin / editor / member
- **权限申请**: UserPermission + AccessRequest 模型，8 个 API
- **权限中心页面**: `/permissions`
- **上传权限**: editor+ 可上传

### 6.4 AI 智能分析
- **图像**: Qwen VL 视觉识别 → 摘要+标签+分类
- **文档**: PDF/Word/PPT/Excel/TXT → 文本提取+AI摘要
- **视频/音频**: Whisper 转录 + AI 摘要
- **向量搜索**: DashScope text-embedding-v3 (1024维) → pgvector

### 6.5 水印下载
- 图片/PDF 下载时叠加 WAIC logo + 日期水印
- 在线浏览无水印
- 通过 `?dl=1` 参数触发

### 6.6 文件格式扩展
- 支持: Word(doc/docx), PPT(ppt/pptx), Excel(xls/xlsx), PDF, TXT/MD/CSV/JSON/XML
- Word 全文搜索: python-docx 提取正文 → pgvector 索引

### 6.7 其他
- **字幕搜索**: 搜索结果展示匹配字幕片段+时间戳跳转
- **通知铃铛**: 动态计数，30 秒轮询
- **分类中文化**: 数据库直接改分类名
- **在线剪辑**: 集成剪神编辑器，去品牌化
- **分享弹窗**: 复制链接 + 视频时间戳
- **视频精准 Seek**: 自定义 Range 请求中间件

---

## 七、开发指南

### 7.1 修改 CSS/主题
- 改 `static/css/waic-theme.css`（最后加载，优先级最高）
- **不要手改** `static/css/_commons.css`（Webpack 编译产物）
- 不要改 `frontend/src/static/css/` 下的 SCSS（主题变量是死代码）
- 改完清浏览器缓存（CSS 缓存极顽固）

### 7.2 修改 Django 后端
- 改 `cms/local_settings.py` 不需要重启（Django 自动检测）
- 改 `files/` 下的 views/models 需要手动重启（`--noreload` 模式）
- 改模板 `templates/` 建议重启

### 7.3 修改 React 前端
```bash
cd frontend
npm run dist
cp -r dist/static/* ../static/
# 重启 Django
```

### 7.4 添加新功能
- 在 `files/` app 内扩展，不要新建 Django app
- 路由注册在 `files/urls.py`
- 页面视图在 `files/views/pages.py`
- API 视图在 `files/views/media.py`
- 通知联动在 `files/methods.py` 的 `notify_users()`

### 7.5 测试
```bash
# 验证 Django 无错误
python manage.py check --deploy

# 验证 API
curl http://localhost:8005/api/v1/media/

# 验证静态文件
curl -I http://localhost:8005/static/css/waic-theme.css
```

---

## 八、已知问题 & 注意事项

### 8.1 架构问题
- **CSS 四体系混战**: SCSS 编译 → `_commons.css` → `waic-theme.css` !important 硬覆盖 → `add-media.css`。SCSS 主题变量是死代码，统一方案见 `references/css-architecture-unification.md`
- **React 版本老旧**: React 17 + Flux（非现代 Redux/MobX），TypeScript 5.9 有类型冲突
- **Django dev server 不支持 Range 请求**: 视频 seek 需要 `cms/range_serve.py` 中间件

### 8.2 环境问题
- **WSL 跨文件系统慢**: /mnt/h/ 上所有操作都慢，runserver 必须 `--noreload`
- **Celery worker PATH**: 子进程不继承 venv/bin，需 `WHISPER_BIN` 绝对路径
- **CSS 缓存顽固**: 浏览器可能缓存旧 CSS，需强制刷新或模板内联注入

### 8.3 数据库
- **向量维度**: DashScope embedding 是 1024 维（不是 1536）
- **中文搜索**: PG `simple` 分词器不认中文，加了 `icontains` 兜底
- **转录后同步**: transcript_text + subtitle_text + update_search_vector 三件套缺一不可

---

## 九、参考资料

Skill 目录下有 21 篇参考文档：

| 文档 | 内容 |
|------|------|
| `full-feature-audit.md` | 全功能代码审计（25页面+30API） |
| `tech-stack-audit.md` | 技术栈全景分析 + CSS 四体系混战 |
| `css-architecture-unification.md` | CSS 统一方案 |
| `permissions-architecture.md` | 权限体系设计 |
| `permissions-system.md` | 权限申请系统架构 |
| `watermark-download.md` | 水印下载实现 |
| `clip-editor-integration.md` | 剪神编辑器集成 |
| `subtitle-search-debugging.md` | 字幕搜索调试指南 |
| `django-range-serve.md` | 视频 Range 请求修复 |
| `ai-tagging-prompt-design.md` | AI 标签/分类 Prompt 设计 |
| `upload-design-critique.md` | 上传页设计评审 |
| `share-popup-review.md` | 分享弹窗审查 |
| `share-link-analysis.md` | 分享链接分析 |
| `sidebar-header-customization.md` | 侧边栏/顶栏定制 |
| `css-caching-and-inline-fix.md` | CSS 缓存修复方案 |
| `multilingual-fix.md` | 多语言修复 |
| `frontend-architecture.md` | 前端架构 |
| `architecture-overview.md` | Docker 打包方案 |
| `stitch-mcp-setup.md` | Stitch MCP 设计工具设置 |
| `stitch-homepage-redesign.md` | Stitch 首页重设计 |
| `clip-editor-architecture.md` | 编辑器架构 |

这些文档位于 Hermes skill 目录：`~/.hermes/skills/software-development/waic-media-platform/references/`

---

## 十、快速命令速查

```bash
# 启动服务器
python manage.py runserver 0.0.0.0:8005 --noreload

# 停止服务器
pkill -9 -f "manage.py runserver"

# 前端编译
cd frontend && npm run dist && cp -r dist/static/* ../static/

# Celery Worker
celery -A cms worker -Q long_tasks,short_tasks -l INFO --concurrency=2

# 数据库检查
python manage.py check --deploy
python manage.py showmigrations

# 清理静态文件缓存
python manage.py collectstatic --noinput --clear

# APT 依赖（Ubuntu）
sudo apt install postgresql redis-server ffmpeg bento4
```
