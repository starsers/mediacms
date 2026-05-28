# Clip Editor (剪神) 架构分析

## 路由
- `/clip/` — 主页面，Django 模板 `templates/cms/clip.html`
- `/clip/editor/` — iframe 内容，Vue.js 编译产物 `/static/jianshen/index.html`

## 页面结构
```
┌───────────────┬──────────────────────────────┐
│ 左侧素材库    │ 右侧编辑器（iframe）          │
│ (Django SSR)  │ /static/jianshen/             │
│               │  "视频编辑软件v1.0"            │
│ 📁 我的素材   │  Vue 3 + 编译 JS              │
│ 搜索框        │  ┌──────────────────────┐     │
│ 素材列表      │  │                      │     │
│  - 预览/下载  │  │   拖入素材开始剪辑    │     │
│  - 上传按钮   │  │                      │     │
│               │  └──────────────────────┘     │
└───────────────┴──────────────────────────────┘
```

## 素材列表数据源
JavaScript 通过 `fetch('/api/v1/media?limit=50')` 获取媒体列表。
每条素材有 `media_file_url` 可供播放/下载。

## 侧边栏折叠
已实现 CSS class toggle: `#clip-sidebar.collapsed` → `width: 32px`。

## 拖拽到编辑器需求分析
用户想要从左侧素材库直接拖素材到右侧编辑器，而不是从本地电脑拖文件。

### 技术路径
1. **父页面**（`clip.html`）: 素材列表加 `draggable="true"` + `dragstart` 事件携带 media URL
2. **iframe 通信**: 用 `window.postMessage` 传递 URL 给 `/clip/editor/` iframe
3. **编辑器接收**: 编译后的 Vue.js 需要能接受外部 URL（而不是只接受本地 File 对象）

### 难度评估
- 父页面改动: **低**（加 drag 事件 + postMessage）
- 编辑器改动: **高**（Vue 编译产物，无源码，需 patch 已编译 JS 或替换编辑器）
