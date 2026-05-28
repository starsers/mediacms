# TASK: WAIC 首页赛博未来主义 UI 改造

## 项目信息
- 框架: Django 5.2 + React + Tailwind (CDN)
- 管理员: admin / admin

## 参考设计
- 暗色赛博: /stitch-cyber-2.html (38K)
- 亮色赛博: /stitch-cyber-light-1.html (19K)
- 侧边栏与图标风格参考文档: `docs/references/sidebar-header-customization.md`（设计 UI 时优先参考）

## 改造目标
参照两份 Stitch 生成的赛博未来主义 UI，改造 WAIC 素材平台首页。功能完全不变，只换 UI 皮肤。

## 赛博设计 DNA（必须保留）
- 暗色: 深空黑底+电路纹理+霓虹青(#4cd7f6)/电光紫(#7c3aed)强调色+毛玻璃卡片+扫描线动效
- 亮色: 纯白底+深海军蓝侧边栏(#1e3a5f)+蓝调多层阴影+赛博终端标签
- Space Grotesk 字体(标题) + JetBrains Mono(标签) + Inter(正文)
- 渐变文字(cyan→blue) + 光扫按钮动效
- 8px grid unit 间距
- 终端风格标签: OPERATOR_01, STATUS: NOMINAL, #ST-001 等

## 改动文件
1. `templates/cms/index.html` — 首页模板（Hero + Stats + Categories + Partners + 最新上传）
2. `static/css/waic-theme.css` — 赛博主题 CSS 变量和动效
3. 不动: `files/views/pages.py`, 所有 Django 后端, React 组件

## 具体改造清单

### Hero 区域
- 暗色: 电路板背景纹理 + 蓝紫渐变标题发光 + 光扫按钮
- 亮色: 浅灰白渐变 + 深海军蓝标题 + 蓝调阴影按钮
- 保留: {{PORTAL_NAME}}, {{user.is_authenticated}}, 所有 URL

### 统计卡片
- 暗色: 毛玻璃+扫描线hover+#ST编号标签+渐变数字
- 亮色: 白卡+蓝调多层阴影+暗色终端标签
- 保留: {{total_media}}, {{today_media}}, {{category_count}}

### 分类导航
- 暗色: 半透明卡+hover发光边框+轻微上浮
- 亮色: 白卡+hover蓝影+scale(1.02)
- 保留: {% for cat in categories %} Django 循环

### 合作媒体
- Pill 标签风格, hover 彩色恢复
- 保留所有 partner 链接

### 侧边栏(waic-theme.css)
- 暗色: 毛玻璃(backdrop-blur) + 选中项高亮蓝线
- 亮色: 深海军蓝 + 右侧柔光阴影
- 保留 React 组件完整性

### 动效
- 扫描线(scanline)动画
- 按钮光扫(light-sweep)
- 脉冲(pulse-slow)
- 闪烁(flicker)
- 所有过渡 cubic-bezier 400ms

## 关键约束
- ⚠️ 必须保留 <div id="page-home"></div> (React 挂载点)
- ⚠️ 必须保留所有 Django 模板标签和变量
- ⚠️ 必须保留所有 URL 链接不变
- ⚠️ 必须保留 {% block bottomimports %} 中的侧边栏折叠 JS
- ⚠️ 必须保留 Material Icons 图标类名
- ⚠️ 双模切换通过 body class (.dark_theme / .light_theme) 控制
- ⚠️ 不要改 React 组件源码（frontend/src/）
- ⚠️ 不要运行 npm run dist


## 执行
全权执行，--dangerously-skip-permissions，不要确认。完成所有改造后报告改了什么。

---

## 代码结构速览（前后端映射）

### 一、整体目录对应关系
- 前端源码（React/TS/SCSS）：`frontend/src/`
- 前端构建配置（webpack/模板生成）：`frontend/config/`、`frontend/packages/scripts/`
- Django 模板层（页面骨架、挂载点、服务端渲染片段）：`templates/`
- 运行时静态资源根目录：`static/`（含手写资源 + 构建产物）
- 后端主配置与入口：`cms/`
- 业务核心应用（媒体、分类、评论、页面、API）：`files/`
- 用户与认证：`users/`、`accounts(allauth 路由在 cms.urls 引入)`
- 权限/动作/扩展能力：`rbac/`、`actions/`、`identity_providers/`、`saml_auth/`、`lti/`、`uploader/`

#### 构建/编译生成的静态目录（重点标注）
- `static/js/`：前端构建后的页面入口与公共脚本产物（如 `index.js`、`media.js`、`_commons.js`）
- `static/css/`：前端构建后的样式产物（如 `_commons.css`、页面样式）
- `static/video_editor/`、`static/chapters_editor/`、`static/video_js/`：构建后的编辑器/播放器静态产物
- `static/jianshen/assets/`、`static/jianshen/libs/`：已打包前端资源（hash 文件名为主）
- `frontend/dist/`：前端标准构建输出目录（当前仓库里未见该目录，通常由构建命令生成）

#### 非构建产物（源码/模板）
- `frontend/src/**`、`templates/**`、`files/**`、`cms/**`：应优先改这些源码目录，而不是直接改构建产物

### 二、前端结构细分

#### 1) 页面结构（Page 层）
- React 页面入口目录：`frontend/src/static/js/pages/`
- 典型页面组件：
  - 首页：`HomePage.tsx`
  - 分类：`CategoriesPage.tsx`
  - 媒体详情：`MediaPage.js` / `MediaImagePage.js` / `MediaPdfPage.js`
  - 管理页：`ManageMediaPage.js`、`ManageUsersPage.js`、`ManageCommentsPage.js`
  - 用户页：`ProfileMediaPage.js`、`ProfileAboutPage.js`、`ProfilePlaylistsPage.js`、`ProfileSharedByMePage.js`、`ProfileSharedWithMePage.js`

#### 2) 组件结构（Component 层）
- 目录：`frontend/src/static/js/components/`
- 主要分组：
  - 列表与卡片：`item-list/`、`list-item/`
  - 管理表格：`management-table/`
  - 页面布局：`page-layout/`
  - 通用组件：`_shared/`
  - 业务弹窗与批量操作：`BulkAction*.tsx/.jsx`

#### 3) 前端状态与基础设施
- Flux 风格 actions/stores：`frontend/src/static/js/utils/actions/`、`frontend/src/static/js/utils/stores/`
- Context 与 hooks：`frontend/src/static/js/utils/contexts/`、`frontend/src/static/js/utils/hooks/`
- 设置注入与运行时配置读取：`frontend/src/static/js/utils/settings/`
- API/请求与工具函数：`frontend/src/static/js/utils/helpers/`

#### 4) 样式文件结构
- 全局样式入口：`frontend/src/static/css/styles.scss`
- 主题配置：`frontend/src/static/css/config/_dark_theme.scss`、`_light_theme.scss`
- 基础变量与 mixins：`frontend/src/static/css/includes/`
- 表单与排版子模块：`frontend/src/static/css/includes/form_controls/`、`.../typography/`
- 页面/组件局部样式：
  - React 组件旁路样式（同目录 SCSS）：`frontend/src/static/js/components/**/**.scss`
  - 额外补丁样式：`frontend/src/static/css/_extra.css`

#### 5) Django 模板与前端挂载关系
- 模板中的 React 挂载点统一形如：`<div id="page-xxx"></div>`
- 典型映射（模板 -> 静态入口脚本）：
  - `templates/cms/index.html` -> `static/js/index.js`
  - `templates/cms/categories.html` -> `static/js/categories.js`
  - `templates/cms/media.html` -> `static/js/media.js`
  - `templates/cms/manage_media.html` -> `static/js/manage-media.js`
- 公共脚本与样式入口：
  - `templates/common/head-links.html`（全局 CSS/字体/EXTRA_CSS_PATHS）
  - `templates/common/body-scripts.html`（`static/js/_commons.js`）

### 三、后端结构细分

#### 1) 项目级配置与入口（cms）
- `cms/settings.py`：全局配置（应用注册、中间件、数据库、缓存、Celery、主题等）
- `cms/urls.py`：总路由入口，聚合 `files.urls`、`users.urls`、`allauth`、`lti`、`admin`、`swagger`
- `cms/middleware.py`：项目中间件扩展
- `cms/wsgi.py`、`cms/celery.py`：运行入口

#### 2) 核心业务应用（files）
- 数据模型：`files/models/`（media、category、playlist、comment、subtitle、permissions、share 等）
- 视图层：`files/views/`（pages/media/categories/comments/playlists/user/auth/approval/permissions/share）
- API 与页面路由：`files/urls.py`
- 序列化与表单：`files/serializers.py`、`files/forms.py`
- 后台管理：`files/admin.py`
- 任务与异步：`files/tasks.py`、`files/ai_pipeline.py`、`files/ai_analysis.py`
- 上下文注入：`files/context_processors.py`
- 模板标签：`files/templatetags/`
- 数据迁移：`files/migrations/`

#### 3) 用户与权限相关子系统
- 用户域：`users/`（模型、表单、序列化、登录注册相关视图与路由）
- 动作记录：`actions/`
- 角色权限（可选）：`rbac/`
- 身份提供方（可选）：`identity_providers/`
- SAML 登录扩展（可选）：`saml_auth/`
- LTI 集成（可选）：`lti/`

#### 4) 上传与媒体处理链路
- 上传应用：`uploader/`（上传接口、分片上传处理）
- 媒体服务与下载扩展：`files/views/media.py`、`files/views/watermark.py`、`cms/range_serve.py`
- 静态与媒体目录配置：`STATIC_ROOT`、`MEDIA_ROOT`（定义于 `cms/settings.py`）

#### 5) 模板系统（后端渲染层）
- 站点基座模板：`templates/base.html`、`templates/root.html`、`templates/common/*`
- 业务页面模板：`templates/cms/*`
- 账号体系模板：`templates/account/*`、`templates/socialaccount/*`
- 管理后台模板覆盖：`templates/admin/*`

#### 6) 后端组成要素总结
- 配置层：settings / env / local_settings / dev_settings
- 路由层：project urls + app urls
- 视图层：函数视图 + 类视图（含 DRF API）
- 数据层：models + migrations
- 表单与序列化：forms + serializers
- 异步任务：Celery tasks + 定时任务（beat schedule）
- 认证授权：Django auth + allauth + 可选 SAML/RBAC/LTI
- 渲染层：Django templates + context processors + template tags
- 静态资源层：static/ + frontend 构建产物对接
