# WAIC MediaCMS — 任务清单

> 调用方式：
> 1. **Plan**：`claude -p "分析 TASK.md 里面「XXX」这个任务，制定详细实施方案写到 plan 文件，不要改代码" --print`
> 2. **Execute**：`claude -p "按照刚才的方案，执行 TASK.md 里面「XXX」" --dangerously-skip-permissions`
>
> 引用任务时按描述内容引用，不按编号。

---

## 主页布局对齐

Hero 横幅 + 分类导航区域在 `waic-home-page`（max-width: 1200px）内居中，但下面 React 渲染的「推荐」和「最新」区域宽度不同（约 1300px），导致四块视觉错位。

目标：首页从上到下（Hero → 分类 → 推荐 → 最新）全部对齐到同一个最大宽度（1200px 或 1308px，与现有 waic-home-page 保持一致）。

涉及文件：
- `frontend/src/static/js/components/page-layout/PageMain.jsx`
- `frontend/src/static/css/waic-theme.css` 或对应的 SCSS

验证：刷新 http://localhost:8005/，四块内容左右边缘对齐。

---

## 剪辑页拖拽素材到编辑器

`/clip/` 页面左侧有素材库列表，右侧是 iframe 嵌入的剪神编辑器。目前素材库里的文件只能「下载到本地，再从文件系统拖入 iframe」，操作太绕。

目标：用户从左侧素材列表直接拖一个素材卡片到右侧编辑器区域，素材自动加载到剪神编辑器中。

涉及文件：
- `templates/cms/clip.html`（素材列表渲染在 `renderMediaList()` 函数中）

技术约束：
- 剪神编辑器是编译后的 Vue 应用（`static/jianshen/`），不能改源码
- 需要通过 `postMessage` 在父页面和 iframe 之间通信
- 素材卡片需要加 `draggable` 属性和 `dragstart` 事件
- iframe 外层需要监听 `dragover` / `drop` 事件
- 需要了解剪神编辑器 iframe 内部是否暴露了接收外部 URL 的 API

备选方案：如果 iframe 不接收 postMessage，可在父页面 fetch 素材 → 转 blob URL → 通过某种方式注入 iframe。

验证：打开 http://localhost:8005/clip/，从左侧素材拖一个视频到编辑器，素材出现在编辑器中。
