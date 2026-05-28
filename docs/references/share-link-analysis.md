# 分享链接功能 — 现状分析与实现方案

> 2026-05-21 基于代码审查的精确缺口分析

## 现有代码状态

### 后端（全写完，缺路由）

| 组件 | 文件 | 状态 |
|---|---|---|
| `SharedLink` 模型 | `files/models/share.py` | ✅ 完整 — UUID token、密码(hash)、过期、最大访问次数、三级权限(view/download/edit)、访问统计 |
| `ShareCreate` API | `files/views/share.py:20` | ✅ 类已写好，POST 创建分享链接 |
| `ShareAccess` API | `files/views/share.py:77` | ✅ 路由 `s/{token}/` 已注册 — GET验证/POST密码解锁 |
| `ShareList` API | `files/views/share.py:136` | ✅ 类已写好，GET列表 + DELETE删除 |
| 路由 | `files/urls.py` | ❌ **ShareCreate 和 ShareList 缺路由** |

### 前端（仅社交分享）

| 组件 | 说明 |
|---|---|
| `MediaShareButton.jsx` | 触发弹窗，只有 Embed + Email 两种模式 |
| `MediaShareOptions.jsx` | 弹窗内容：社交分享按钮 + 复制链接 + "Start at"时间戳 |
| `MediaShareEmbed.jsx` | iframe嵌入代码生成 |

**现有分享按钮不涉及 SharedLink 模型**——只是复制媒体URL或生成嵌入代码。

### 与旧版分享的区别

MediaCMS 原生有一套用户间分享机制（`views.media_share` 在 `media.py:1307`，通过 `api/v1/media/{token}/share` 路由），publish状态页有 shared/unshared 复选框。这套机制跟新的 `SharedLink`（Token链接分享）是**两套独立系统**，不冲突。

---

## 实现方案

### 1. 路由注册（`files/urls.py`）

```python
# ===== Share API =====
re_path(r"^api/v1/share/create/$", share_views.ShareCreate.as_view(), name="api_share_create"),
re_path(r"^api/v1/share/list/$", share_views.ShareList.as_view(), name="api_share_list"),
re_path(r"^s/(?P<token>[\w\-]+)/$", share_views.ShareAccess.as_view(), name="shared_media"),
```

### 2. 媒体详情页 — 创建分享入口

**位置**：媒体详情页 `view?m=xxx` 的 actions 栏

**入口1 — WAIC actions 区**（`MediaWaicActions.jsx`）：
在现有的「归档」「转录」「降噪」按钮旁加「🔗 分享」按钮

**入口2 — 分享弹窗内**（`MediaShareOptions.jsx`）：
在现有 "Share media" 标题下方、社交分享按钮下方，加一个**「创建分享链接」区块**：
- 权限下拉：仅查看 / 可下载 / 可编辑
- 密码输入框（可选）
- 过期天数（可选，默认7天）
- 最大访问次数（可选）
- 创建按钮 → `POST /api/v1/share/create/`
- 创建成功后显示链接 + 一键复制 + 「链接已创建」提示

### 3. 个人工作台 — 我的分享管理

**入口**：个人工作台 `/notifications` 页面旁，顶栏头像下拉菜单

**页面**：`/my-shares` — 表格列表
- 素材名（链接到素材详情）
- 分享链接（可复制）
- 权限级别
- 访问次数 / 上限
- 是否过期
- 创建时间
- 删除按钮（`DELETE /api/v1/share/list/`）

### 4. 分享链接着陆页

**路由已存在**：`s/{token}/`

需要前端模板 `templates/cms/share_landing.html`：
- 有密码 → 显示密码输入框
- 已过期 → 显示过期提示
- 正常 → 显示素材预览（根据权限级别）

---

## 涉及文件清单

| 文件 | 改动 |
|---|---|
| `files/urls.py` | +2 行路由 |
| `frontend/src/.../MediaShareOptions.jsx` | 加创建分享链接区块 |
| `frontend/src/.../MediaWaicActions.jsx` | 加分享按钮入口 |
| `frontend/src/.../ListItem.jsx` | 搜索结果列表页分享入口（可选） |
| `templates/cms/share_landing.html` | 新建，分享链接着陆页 |
| `templates/cms/my_shares.html` | 新建，我的分享管理页 |
| `files/views/pages.py` | 加 `my_shares` 视图 |
| `files/views/__init__.py` | 导出新视图 |
| `files/urls.py` (页面路由) | 加 `/my-shares` 页面路由 |
| `static/css/waic-theme.css` | 分享相关样式 |
| `frontend/` | `npm run dist` 编译 |
