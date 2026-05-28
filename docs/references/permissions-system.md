# 权限申请系统完整架构

## 数据模型

### UserPermission（管理员授权的权限记录）
- `user` (FK) — 被授权用户
- `media` (M2M) — 特定素材
- `category` (M2M) — 整个分类
- `tags` (M2M) — 带有这些标签的素材
- `can_download` (bool) — 下载权限
- `can_upload` (bool) — 上传权限
- `granted_by` (FK) — 授权人

### AccessRequest（用户申请的权限请求）
- `user` (FK) — 申请人
- `scope_type` — media / category / tag / upload
- `media` / `category` / `tag` (FK, nullable)
- `status` — pending / approved / rejected
- `reason` (驳回原因)
- `reviewed_by` / `reviewed_at`

## API 端点

```
POST /api/v1/perm/request/          # 申请素材/分类/标签的下载剪辑权限
POST /api/v1/perm/request_upload/   # 申请上传权限（全局，无 scope）
POST /api/v1/perm/approve/          # admin 审批（approve/reject）+ 发通知
POST /api/v1/perm/grant/            # admin 直接授权 → 创建 UserPermission
GET  /api/v1/perm/pending/          # admin 查看待审批列表
GET  /api/v1/perm/check/?media_id=X # 查用户对某素材的权限（media/category/tag 三级匹配）
GET  /api/v1/perm/my/               # 我的权限清单
GET  /api/v1/perm/history/          # 我的申请记录
```

## 通知联动

`files/methods.py` `notify_users` 新增三个 action 分支：
- `access_requested` → 通知 admin / 配置的审批人
- `access_approved` → 通知申请人（extra 传 username）
- `access_rejected` → 通知申请人

## 前端页面

### 权限中心 `/permissions`
- Django 模板 `templates/cms/permissions.html` + 原生 JS
- 视图 `files/views/pages.py` `permissions_center()`
- 路由 `files/urls.py` `^permissions$`
- 侧边栏入口：`SidebarNavigationMenu.jsx` — 所有登录用户可见

### 素材页快捷申请按钮
- 注入脚本在 `templates/cms/media.html`（`{% block bottomimports %}`）
- 仅 member（非 admin/editor）且无下载权限时显示橙色 `🔒 申请权限` 按钮
- 弹出对话框：`申请此素材的下载/剪辑权限` + `前往权限中心`
- 需要 `media_id` 从 Django 模板上下文传入（`context["media_id"] = media.id`）

## 关键踩坑

1. **`request.user.role` 不存在** — 用 `getattr(request.user, 'is_editor', False)`
2. **API 字段名不匹配** — 素材详情 API 返回 `categories_info`/`tags_info`（只有 title/url，无 id），别用它取 ID。用 Django 模板传 `media_id` 到 JS。
3. **通知原来形同虚设** — `request_access` 调了 `notify_users` 但后者无 `access_requested` 处理分支，不写 Notification 表。已修复。
4. **`approve_access` 审批后缺通知** — 已补 `access_approved`/`access_rejected` 通知

## 待做

- admin 审批操作面板（API 就绪，缺前端审批界面）
