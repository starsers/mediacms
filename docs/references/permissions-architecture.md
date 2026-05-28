# WAIC 权限体系完整分析 (2026-05-20)

## 一、用户角色层级

| 角色 | User 模型字段 | 权限逻辑 |
|------|-------------|---------|
| **Superuser** | `is_superuser=True` (Django AbstractUser) | 上帝模式，所有操作 |
| **Manager** | `is_manager=True` (MediaCMS 自定义) | 管理所有媒体 + 用户 |
| **Editor** | `is_editor=True` (MediaCMS 自定义) | 管理所有媒体（不能管用户） |
| **Member** | 以上全 False | 普通成员，默认只能看 listable=True 的公开内容 |

权限判断函数 (`files/methods.py`):
- `is_mediacms_editor(user)` = `user.is_superuser or user.is_manager or user.is_editor`
- `is_mediacms_manager(user)` = `user.is_superuser or user.is_manager`

## 二、注册流程

```
用户访问 /accounts/signup/
  → USERS_CAN_SELF_REGISTER = True (settings.py:147)
  → ALLOWED_DOMAINS_FOR_USER_REGISTRATION = [] (不做域名限制)
  → MyAccountAdapter.is_open_for_signup() returns USERS_CAN_SELF_REGISTER
  → SignupForm 收集 name + email + password
  → User.objects.create_user() → 创建记录
  → USERS_NEEDS_TO_BE_APPROVED = False → 直接激活，无需审批
  → 默认: is_editor=False, is_manager=False, is_approved=False
  → 结果: 纯 member 角色，只能看公开内容
```

## 三、管理员赋权机制（两种平行的方式）

### 方式 A：提升角色级别（改 User 表字段）
- 在 Django Admin (`/admin/users/user/`) 勾选 `is_editor` 或 `is_manager`
- `is_superuser` + `is_staff` 在 `/admin/auth/user/` 设置
- 效果: editor → 能浏览/管理所有媒体，不需要任何 UserPermission

### 方式 B：精细资源级赋权（UserPermission 模型）
- 文件: `files/models/permissions.py`
- API: `files/views/permissions.py`（grant_permission, approve_access）
- 维度: media (M2M) / category (M2M) / tags (M2M) — 三选一或多选
- 开关: `can_download` (默认 True), `can_upload` (默认 False)
- 管理员在 UserPermission Admin 操作，支持 filter_horizontal 多选

```python
class UserPermission(models.Model):
    user = FK(User)          # 被赋权的成员
    media = M2M(Media)       # 具体素材
    category = M2M(Category) # 整个分类
    tags = M2M(Tag)          # 带某标签的所有素材
    can_download = Boolean(default=False)  # 能否下载
    can_upload = Boolean(default=False)    # 能否上传
    granted_by = FK(User)    # 谁赋权的（管理员）
```

## 四、AccessRequest — 成员主动申请权限

- 文件: `files/models/permissions.py` (AccessRequest 模型)
- API: `files/views/permissions.py` (request_access, approve_access)
- 流程: member 申请 → admin 审批 → 批准后自动创建 UserPermission
- 审批人: `APPROVAL_REVIEWER = "admin"` (local_settings.py:117)

## 五、RBAC 分组（高级特性，仅 IDP 场景生效）

- 文件: `rbac/models.py`
- 模型: RBACGroup (uid, name, categories, identity_provider) + RBACMembership (user, role, group)
- 角色: MEMBER / CONTRIBUTOR / MANAGER
- 触发条件: `settings.USE_IDENTITY_PROVIDERS = True`

## 六、上传权限

- 配置: `CAN_ADD_MEDIA = "all"` (settings.py:16)
- local_settings 未覆盖 → 所有人可上传
- 逻辑: `files/methods.py` `can_add_media(request.user)` 检查 `CAN_ADD_MEDIA`
- UserPermission.can_upload 字段存在但 **未被任何视图调用**（形同虚设）

## 七、下载权限

- UserPermission.can_download 字段存在
- API 检查: `/api/v1/perm/check?media_id=N` → `check_permission()` 视图
- **下载视图未强制执行** — 知道文件 URL 即可直接下载
- Editor/Manager 跳过所有权限检查

## 八、内容可见性

| 场景 | 检查机制 |
|------|---------|
| 公开素材 | `listable=True` — 所有人可见 |
| 私密素材 | `MediaPermission` (M2M) 或 `UserPermission.media` 或 `is_editor` |
| 搜索 | `basic_query = Q(listable=True) \| Q(permissions__user=request.user) \| Q(user=request.user)` |
| RBAC 扩展 | `Q(category__in=rbac_categories)` (仅当 `USE_RBAC=True`) |

## 九、成员列表可见性

- 配置: `CAN_SEE_MEMBERS_PAGE = "editors"` (local_settings.py:122)
- 选项: "all" / "editors" / "admins"
- context_processors 暴露 `canSeeMembersPage` 给模板

## 十、当前缺口

| # | 问题 | 严重度 | 修复建议 |
|---|------|--------|---------|
| 1 | `CAN_ADD_MEDIA="all"` 所有人可上传 | 🔴 | 改为 `"editors"` 限制 editor+ 才能上传 |
| 2 | `can_download` 不强制 | 🔴 | 下载视图加 `UserPermission` 检查 |
| 3 | `can_upload` 字段未被调用 | 🟡 | 上传视图引用 `UserPermission.can_upload` |
| 4 | 缺"只读"角色 | 🟡 | member 被赋权后能下载，无法设置"只能看不能下" |
| 5 | 角色 vs 精细赋权是平行线 | 🟢 | editor 看到一切，UserPermission 对 editor 不生效（设计如此） |

## 十一、改进建议（WAIC 内部素材管理场景）

**目标角色**：管理员 / 编辑 / 嘉宾 / 媒体伙伴

| 角色 | 看公开 | 看私密 | 上传 | 下载 | 赋权方式 |
|------|--------|--------|------|------|---------|
| 管理员 | ✅ | ✅ | ✅ | ✅ | is_manager=True |
| 编辑 | ✅ | ✅ | ✅ | ✅ | is_editor=True |
| 嘉宾/伙伴 | ✅ | ✅(被授予) | ❌ | ✅(被授予) | UserPermission |

**需要改动的**：
1. `CAN_ADD_MEDIA` 改为 `"editors"` → local_settings.py
2. 下载视图加 `can_download` 检查 → files/views/media.py
3. 注册后默认无上传/下载权限 → 已是现状

## 关键文件索引

| 组件 | 文件 |
|------|------|
| User 模型 | `users/models.py` |
| 权限模型 | `files/models/permissions.py` |
| MediaPermission | `files/models/media.py:1063` |
| 权限 API | `files/views/permissions.py` |
| 权限判断函数 | `files/methods.py` (is_mediacms_editor/manager) |
| RBAC 模型 | `rbac/models.py` |
| 注册适配器 | `users/adapter.py` |
| 注册表单 | `users/forms.py` |
| 审批配置 | `cms/local_settings.py` (APPROVAL_REVIEWER, MEDIA_IS_REVIEWED) |
| 上传权限 | `cms/settings.py` (CAN_ADD_MEDIA) |
| 成员可见性 | `cms/local_settings.py` (CAN_SEE_MEMBERS_PAGE) |
