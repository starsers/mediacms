# WAIC 素材平台 v7 完整功能审计 (2026-05-19)

## 一、核心架构

| 组件 | 技术 |
|---|---|
| 框架 | Django 5.2 + DRF + React / Webpack |
| DB | PostgreSQL `mediacms_v7` @ localhost:5432 |
| 缓存 | Redis DB 2 @ localhost:6379 |
| Celery 队列 | `short_tasks`, `long_tasks`, `celery` (3 队列) |
| 前端编译 | `frontend/` npm webpack → `static/` |
| 静态文件 | `STATICFILES_DIRS = ['static/']`, `STATIC_ROOT = 'static_collected/'` |

**Django Apps（8个）:** `files`, `users`, `actions`, `rbac`, `uploader`, `identity_providers`, `lti`, `saml_auth`

## 二、媒体管理 (files app)

### 模型 (23个)
- `Media` — 核心媒体模型 (AI 字段: allow_whisper_transcribe, media_info)
- `Category` — 扁平分类（子分类通过 `"父 > 子"` 命名约定）
- `Tag` — AI 标签
- `Comment` — MPTT 嵌套评论 + @提及通知
- `Playlist` / `PlaylistMedia` — 播放列表
- `EncodeProfile` / `Encoding` — 编码配置与任务
- `Subtitle` / `Language` — 字幕
- `TranscriptionRequest` — 转录请求
- `VideoChapterData` / `VideoTrimRequest` — 章节与裁剪
- `MediaPermission` — 媒体访问权限
- `AccessRequest` — 访问申请
- `SharedLink` — 分享链接 (UUID token + 密码 + 过期 + 三级权限)
- `UserPermission` — 用户权限
- `RatingCategory` / `Rating` — 评分
- `Page` / `TinyMCEMedia` — CMS 页面
- `License` — 许可证
- `EmbedMediaCourse` — LTI 嵌入

### 页面 (~27个)

| 页面 | 路由 | 说明 |
|---|---|---|
| 首页 (WAIC定制) | `/` | Hero + 统计 + 分类导航 + React 内容 |
| 精选 | `/featured` | |
| 推荐 | `/recommended` | |
| 最新 | `/latest` | |
| 搜索 | `/search` | 全文搜索 (pgvector) |
| 分类 | `/categories` | |
| 标签 | `/tags` | |
| 媒体详情 | `/view?m=<token>` | 播放/查看页 |
| 上传 | `/upload` | FineUploader 分片上传 |
| 编辑媒体 | `/edit?m=<token>` | 元数据编辑 |
| 替换媒体 | `/replace_media?m=<token>` | |
| 发布 | `/publish?m=<token>` | |
| 编辑章节 | `/edit_chapters?m=<token>` | |
| 编辑视频 | `/edit_video?m=<token>` | |
| 字幕管理 | `/add_subtitle`, `/edit_subtitle` | |
| 播放列表 | `/playlist/<token>` | |
| 分享访问 | `/s/<token>/` | 分享链接着陆页 |
| **在线剪辑** | `/clip/` | 剪神首页 (iframe JianshenVideoEditorWeb) |
| **剪辑编辑器** | `/clip/editor/` | 剪神编辑器 |
| **消息通知** | `/notifications` | 个人工作台 - 消息 |
| **审批中心** | `/approvals` | 个人工作台 - 审批 (通过/驳回按钮) |
| 录屏 | `/record_screen` | |
| 嵌入 | `/embed?m=<token>` | iframe 嵌入代码 |
| 用户主页 | `/user/<username>` | |
| 历史 | `/history` | |
| 喜欢的 | `/liked` | |
| 管理 | `/manage/media`, `/manage/comments`, `/manage/users` | |
| 关于/条款/联系 | `/about`, `/tos`, `/contact` | |
| CMS 页面 | `/<slug>` | 动态页面 |
| Members | `/members` | 成员列表 (权限控制) |
| RSS | `/rss/`, `/rss/search` | |

### API 端点 (~31个)

| 类别 | 端点 | 说明 |
|---|---|---|
| 媒体 CRUD | `api/v1/media`, `api/v1/media/<token>` | 列表/详情 |
| 搜索 | `api/v1/search` | 全文搜索 |
| 媒体操作 | `api/v1/media/<token>/actions` | like/dislike/report |
| 媒体分享 | `api/v1/media/<token>/share` | 分享链接 |
| 章节 | `api/v1/media/<token>/chapters` | 视频章节 |
| 裁剪 | `api/v1/media/<token>/trim_video` | 视频裁剪 |
| 批量操作 | `api/v1/media/user/bulk_actions` | 批量 like/playlist |
| 分类 | `api/v1/categories`, `.../contributor` | |
| 标签 | `api/v1/tags` | |
| 评论 | `api/v1/comments`, `.../media/<token>/comments` | |
| 播放列表 | `api/v1/playlists`, `.../<token>` | |
| 用户操作 | `api/v1/user/action/<action>` | 用户历史 |
| 管理 | `api/v1/manage_media`, `manage_comments`, `manage_users` | |
| 任务 | `api/v1/tasks`, `api/v1/tasks/<token>` | 编码任务 |
| 编码配置 | `api/v1/encode_profiles/` | |
| **审批** | `api/v1/approval/submit`, `approve`, `reject`, `pending` | |
| **归档** | `api/v1/media/<token>/archive/` | toggle_archive |
| **转录** | `api/v1/media/<token>/transcribe/` | 触发 AI 转录 |
| **降噪** | `api/v1/media/<token>/denoise/` | 触发音频降噪 |
| **通知计数** | `api/v1/notifications/count/` | 铃铛角标 |
| **权限** | `api/v1/perm/request`, `approve`, `grant`, `pending`, `check`, `my` | 6 端点 |

## 三、Celery 任务 (19个)

| 任务 | 队列 | 说明 |
|---|---|---|
| `media_init` | short | 媒体上传后初始化 |
| `chunkize_media` | short | 视频切片 |
| `encode_media` | long | 多分辨率编码 (2160p~240p) |
| `create_hls` | long | HLS 流生成 |
| `produce_sprite_from_video` | long | 视频雪碧图 |
| `whisper_transcribe` | long | Whisper 转录 |
| **`transcribe_media`** | long | **DashScope Paraformer 转录** (2026-05-19 新增) |
| **`denoise_media`** | long | **FFmpeg afftdn 降噪** (2026-05-19 新增) |
| `post_trim_action` | short | 裁剪后处理 |
| `remove_media_file` | long | 清理文件 |
| `update_search_vector` | short | 更新 pgvector |
| `update_encoding_size` | short | 更新编码文件大小 |
| `get_list_of_popular_media` | long | 热门媒体计算 |
| `update_listings_thumbnails` | long | 缩略图更新 |
| `save_user_action` | short | 记录用户行为 |
| `check_running_states` | short | 检查编码状态 |
| `check_media_states` | short | 检查媒体状态 |
| `check_pending_states` | short | 检查待处理 |
| `check_missing_profiles` | short | 检查缺失编码配置 |
| `clear_sessions` | short | 清理过期会话 |

## 四、权限体系 (RBAC)

### 角色层级
| 角色 | 数据库 | 权限 |
|---|---|---|
| **member** | `RBACRole.MEMBER` | 仅浏览，无上传/下载/查看 |
| **contributor** | `RBACRole.CONTRIBUTOR` | 可上传、编辑自己媒体 |
| **manager** | `RBACRole.MANAGER` | 管理所有媒体和用户 |

### 权限控制点
- RBAC 分组 (`RBACGroup`) + 分类级访问控制
- `MediaPermission` — 媒体级权限授予
- `AccessRequest` — 访问申请/审批
- `UserPermission` — 用户级权限
- `ApprovalMiddleware` — 用户审批中间件
- **`IPWhitelistMiddleware`** — IP 白名单 (2026-05-19 新增)
- SAML 认证支持
- LTI 学习工具互操作
- 身份提供商 (Identity Providers) 集成

## 五、AI 分析 (DashScope / Alibaba Qwen)

### Pipeline (`files/ai_pipeline.py`)
| 分析类型 | 模型 | 输出 |
|---|---|---|
| 文档 (PDF/Word/PPT/Excel/TXT) | Qwen-Plus | 摘要 + 标签 + 嵌入 |
| 图片 | Qwen VL Plus | 描述 + 物体检测 + 主色 + 标签 |
| 音频 | Paraformer 转录 → Qwen-Plus | 转录稿 + 摘要 + 标签 |
| 视频 | Paraformer 转录 → 关键帧 → Qwen VL Plus | 转录 + 场景描述 + 摘要 + 标签 |

### AI 字段 (Media 模型)
- `media_info` — 元数据 (page_count, author 等)
- `allow_whisper_transcribe` — 转录开关
- 嵌入向量 — 语义搜索 (pgvector)

### AI 前端
- React `MediaWaicActions.jsx` — AI 操作按钮 (归档/转录/降噪)
- `ViewerInfo.js` — AI 元数据面板 (可折叠)
- `ViewerInfoContent.js` — **字幕时间戳可点击跳转** (2026-05-19 新增)

## 六、剪神在线剪辑

- **前端**: Vue.js 独立应用 (JianshenVideoEditorWeb)
- **集成方式**: Django 模板 iframe 嵌入
- **路由**: `/clip/` (首页), `/clip/editor/` (编辑器)
- **素材库**: 左侧面板接入 MediaCMS API
- **部署**: 纯前端静态文件, 不与 MediaCMS React 冲突

## 七、WAIC 品牌定制

| 组件 | 文件 |
|---|---|
| 首页模板 | `templates/cms/index.html` (+ `waic_home.html`) |
| 品牌 CSS | `static/css/_commons.css` (尾部注入) |
| 额外 CSS | `static/css/waic-theme.css` |
| Logo | `static/images/waic-logo-original.png` (1845×330) |
| 管理后台 | Jazzmin + `admin/css/waic-admin.css` |
| 中文本地化 | `files/frontend_translations/zh_hans.py` |
| 通知铃铛 | `templates/config/installation/contents.html` (动态角标) |
| 版权文字 | `SIDEBAR_FOOTER_TEXT = "WAIC 素材平台 © 2026"` |
| **H5 移动端** | `_commons.css` @media (max-width: 767px) (2026-05-19 新增) |
| **IP 白名单** | `cms/middleware.py` IPWhitelistMiddleware (2026-05-19 新增) |
| **审批强制** | `MEDIA_IS_REVIEWED = True` (2026-05-19) |

## 八、2026-05-19 会话修复项

| # | 修复项 | 状态 |
|---|---|---|
| 1 | 边栏底部空白消除 (flexbox + copyright 贴底) | ✅ |
| 2 | 用户头像 → WAIC logo (80×80) | ✅ |
| 3 | 顶栏按钮对齐 (统一 40×40) | ✅ |
| 4 | Document 类型支持恢复 (4 文件修补) | ✅ |
| 5 | `denoise_media` Celery 任务 (FFmpeg afftdn) | ✅ |
| 6 | `transcribe_media` Celery 任务 (DashScope Paraformer) | ✅ |
| 7 | 字幕时间戳点击跳转 (VideoJS seek) | ✅ |
| 8 | 上传审批强制 (`MEDIA_IS_REVIEWED = True`) | ✅ |
| 9 | 铃铛角标动态计数 (`/api/v1/notifications/count/` + 自刷新) | ✅ |
| 10 | 个人工作台页面 (`/notifications`, `/approvals`) | ✅ |
| 11 | IP 白名单中间件 | ✅ |
| 12 | H5 移动端响应式 CSS | ✅ |

## 九、剩余缺口

| # | 问题 | 说明 |
|---|---|---|
| 1 | `SharedLink` API/UI 不完整 | 模型+API类全写完，但 **ShareCreate / ShareList 缺 URL 路由**，前端无创建/管理界面。现有 `MediaShareButton` 只是社交分享(Embed/Email)，不调 SharedLink。详见 `references/share-link-analysis.md` |
| 2 | 水印系统 | **代码中完全不存在**。`ENABLE_WATERMARK` 字符串在项目中搜不到——此前审计记录的"配置预留"不准确。需从零实现显式叠加水印（播放器/图片查看器CSS+JS层） |
| 3 | 审批流转更复杂场景 | 当前为单级审批 (one reviewer) |
| 4 | 消息详情页 | `/notifications` 目前只展示待审批项，非完整消息列表 |
