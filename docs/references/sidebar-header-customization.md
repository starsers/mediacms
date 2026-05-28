# 侧边栏/顶栏 React 组件定制

MediaCMS 的顶栏、侧边栏、页脚均由 React 渲染（`<div id="app-header">` / `<div id="app-sidebar">` / `<div id="app-footer">`）。

## 关键 React 源文件

| 组件 | 文件 |
|------|------|
| 侧边栏导航 | `frontend/src/static/js/components/page-layout/sidebar/SidebarNavigationMenu.jsx` |
| 侧边栏底部版权 | `frontend/src/static/js/components/page-layout/sidebar/SidebarBottom.jsx` |
| 侧边栏主题切换 | `frontend/src/static/js/components/page-layout/sidebar/SidebarThemeSwitcher.tsx` |
| 侧边栏注入导航项 | `frontend/src/static/js/components/page-layout/sidebar/SidebarBelowNavigationMenu.jsx` |
| 顶栏右侧按钮 | `frontend/src/static/js/components/page-layout/PageHeader/HeaderRight.jsx` |
| 顶栏左侧Logo | `frontend/src/static/js/components/page-layout/PageHeader/HeaderLeft.jsx` |
| 页脚容器 | `templates/components/footer.html`（含 `<div id="app-footer">`，可追加 HTML） |
| 配置注入 | `templates/config/installation/contents.html`（注入 header.right / sidebar.footer / sidebar.navMenuItems） |

## 常见定制操作

### 1. 删除顶栏上传按钮
`HeaderRight.jsx` 中删除 `<UploadMediaButton user={user} links={links} />` 行。
保留 `UploadMediaButton` 组件定义不动（侧边栏仍引用）。

### 2. 删除侧边栏底部导航项
`SidebarNavigationMenu.jsx` 第 281 行 return 中删除 `CustomMenuSection()`。
`CustomMenuSection` 硬编码了 About/Terms/Contact/Language 四项。

### 3. 清空侧边栏注入的额外 navMenuItems
`contents.html` 中 `sidebar.navMenuItems` 改为 `[]`。

### 4. 在页脚添加链接
`footer.html` 中在 `<div id="app-footer"></div>` 后追加自定义 HTML。
CSS 放在 `waic-theme.css` 中。

### 5. 侧边栏"上传"高亮
CSS 选择器 `.nav-item-upload-media`，加蓝色半透明背景 + `font-weight:600`。

### 6. 编译
改完 React 源码必须编译：
```bash
cd /mnt/h/media-cms-v7/frontend && npm run dist && cp -r dist/static/* ../static/
```

## UI 风格基线（侧边栏 / 图标）

### 侧边栏风格定位
- 风格类型：**Cyber Futurism + SaaS Dashboard 混合风格**
- 暗色基底：深色高对比背景（深空黑/深海军蓝）
- 强调语言：蓝紫霓虹、激活态高亮、右侧高亮指示线
- 交互语义：圆角胶囊导航项 + hover 提亮 + active 渐变背景

### 图标风格定位
- 图标体系：**Google Material Icons（字体图标）**
- 视觉特征：几何、简洁、功能导向
- 当前实现：保留 Material 图标语义，通过颜色/发光/状态条进行赛博化皮肤增强，而非替换为新图标库

### 后续 UI 设计约束（侧边栏相关）
- 保留 Material Icons 类名与语义映射，不随意更换图标库
- 优先通过颜色、层次、动效做风格强化，避免破坏导航信息架构
- 亮暗双模统一通过 `body.light_theme` / `body.dark_theme` 控制
