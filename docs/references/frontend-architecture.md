# MediaCMS v7 前端架构全分析

> 审查日期: 2026-05-22

## 总览：5 个子系统，实际在用 4 个

| # | 子系统 | 框架 | React版本 | 构建工具 | CSS方案 | 源码位置 | 集成方式 | 状态 |
|---|---|---|---|---|---|---|---|---|
| 1 | **主应用** | React + TS | **17** | Webpack (mediacms-scripts) | SCSS | `/frontend/src/static/js/` | SPA，30页面/85组件，挂在 `#page-*` div | 🔵 核心 |
| 2 | **视频编辑器** | React + TS | **18** | Vite | Tailwind CSS | `/frontend-tools/video-editor/` | 独立SPA，`edit_video.html` 加载 `<div id="video-editor-trim-root">` | 🟡 独立页 |
| 3 | **章节编辑器** | React + TS | **18** | Vite | Tailwind CSS | `/frontend-tools/chapters-editor/` | 独立SPA，`edit_chapters.html` 加载 `<div id="chapters-editor-root">` | 🟡 独立页 |
| 4 | **剪神编辑器** | Vue.js | ? | 未知(无源码) | 编译后CSS | `/static/jianshen/` | `clip_editor` 视图直接 serve `index.html`，注入 `<base>` 标签 | 🔴 黑盒 |
| 5 | **Video.js 播放器** | React + TS | **19** | Vite | SCSS | `/frontend-tools/video-js/` | **零引用** — 代码中没有任何地方加载它 | ⚪ 未使用 |

## 后端：纯 Python，无 Java

| 层 | 技术 | 版本 |
|---|---|---|
| Web框架 | Django | 5.2.6 |
| API | Django REST Framework | 3.16 |
| 异步任务 | Celery | 5.4 |
| 消息队列 | Redis | Alpine |
| 数据库 | PostgreSQL + pgvector | 17.2 |
| 生产服务 | Gunicorn + Nginx + Supervisor | Docker 内 |
| 音视频 | FFmpeg + Bento4 | 静态编译 |
| AI转录 | openai-whisper (本地) | medium 模型 |

## 集成方式：各自独立 SPA，非嵌入式组件

**关键发现**: 各编辑器不是 import 进主应用的 React 组件，而是**完全独立的 SPA**：

1. **主应用**: 通过 `base.html` → `<script src="static/js/media.js">` 加载，渲染到各 `#page-*` div
2. **视频编辑器**: Django view `edit_video()` → `edit_video.html` 模板 → `<script src="static/video_editor/video-editor.js">` → 挂载到 `<div id="video-editor-trim-root">`
3. **章节编辑器**: Django view `edit_chapters()` → `edit_chapters.html` 模板 → `<script src="static/chapters_editor/chapters-editor.js">` → 挂载到 `<div id="chapters-editor-root">`
4. **剪神**: Django view `clip_editor()` → 直接 `open('static/jianshen/index.html').read()` + `<base>` 注入 → `HttpResponse`

它们共享的只是同一个 Django base 模板（顶栏+侧边栏），React 实例互相独立。

## 章节编辑器 vs 视频编辑器：同一代码库的 fork

两者的 `package.json` 都叫 `video-trim-js`，依赖完全一致，目录结构镜像：
```
client/src/
├── App.tsx          ← 不同实现
├── components/       ← 同名文件，内容不同
│   ├── ClipSegments.tsx
│   ├── EditingTools.tsx
│   ├── TimelineControls.tsx
│   └── VideoPlayer.tsx
├── hooks/
│   ├── useVideoChapters.tsx  ← 章节专用
│   └── useVideoTrimmer.tsx   ← 裁剪专用
├── lib/videoUtils.ts         ← 不同实现
├── services/videoApi.ts      ← 不同实现
└── styles/                   ← 不同实现
```

**可以合并**: 两者架构相同（React 18 + Vite + Tailwind），核心组件同名只是实现不同。可合并为一个统一编辑器，用 Tab/模式切换（裁剪 vs 章节）。

## 剪神编辑器：确认无源码

GitHub 仓库 `john70/JianshenVideoEditorWeb` 分析结果：
- **只有编译产物**: `assets/` `cdn/` `libs/` `index.html` `favicon.ico`
- **无源码**: 没有 `src/`、`.vue` 文件、`package.json`、构建配置
- **最后更新**: 2023年7月（3年未动）
- **声明**: "非商业，个人学习目的"
- **结论**: 只能 CSS 覆盖修改，不可改功能

## 统一路线图

| 步骤 | 内容 | 工作量 | 风险 |
|---|---|---|---|
| **第一步** | 章节编辑器 + 视频编辑器合并为一 | 小 | 低 — 同架构、同依赖 |
| **第二步** | 主应用 React 17 → 18 | 中 | 中 — 30页面需回归测试 |
| **第三步(可选)** | 主应用 Webpack → Vite | 大 | 中高 — `mediacms-scripts` 自定义链 |
| **不建议** | 动剪神 | — | 🔴 无源码 |

### 第一步详细：合并编辑器

两个编辑器的共同点：
- 同 React 18 + Vite + Tailwind
- 同 Express SSR 后端
- 同组件结构（只是实现不同）
- 各自构建到独立 static 目录

合并方案：
1. 选一个作为主项目，把另一个的功能作为子路由/Tab
2. 统一 `package.json`，删除重复依赖
3. 修改 Vite 构建配置输出到同一个 static 目录
4. 更新 Django 模板和视图，统一入口 URL
5. 加 Tab 切换：`edit?mode=trim` / `edit?mode=chapters`
