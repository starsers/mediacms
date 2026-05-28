# MediaCMS v7 技术栈审计 (2026-05-26)

## 完整技术栈

### 后端

| 层 | 技术 | 版本 | 备注 |
|----|------|------|------|
| 框架 | Django | 5.2.6 | |
| API | DRF | 3.16.1 | |
| 数据库 | PostgreSQL | mediacms_v7 | |
| 缓存/消息 | Redis | 6379 数据库 1 | |
| 异步任务 | Celery | 5.4.0 | long_tasks + short_tasks 队列 |
| 认证 | django-allauth | 65.4.1 | |
| Admin 皮肤 | django-jazzmin | 3.0.1 | |
| 富文本 | django-tinymce | 4.1.0 | |
| 错误追踪 | Sentry SDK | 2.23.1 | |
| 生产 WSGI | Gunicorn | 23.0.0 | |
| SSO | python3-saml + PyLTI1p3 | 1.16.0 / 2.0.0 | |
| 依赖数 | 27 个 (requirements.txt) | | |

### 前端

| 层 | 技术 | 版本 | 备注 |
|----|------|------|------|
| 框架 | React | **17.0.2** ⚠️ | 2020年发布，已落后3个大版本 |
| 构建 | Webpack 5 | 5.98.0 | |
| 样式源 | SCSS | 55 个源文件 | frontend/src/static/css/ |
| 样式编译 | sass-loader | 1.85.1 | → dist/static/ |
| 手写样式 | static CSS | 15 个文件 | static/css/，含 waic-theme.css |
| 类型 | TypeScript | 5.9.3 | 仅33个文件使用 |
| 状态管理 | **Flux** ⚠️ | 4.0.4 | 已过时，Facebook 不再维护 |
| 测试 | Jest 29 | jsdom | |
| PDF | react-pdf-viewer | 3.9.0 | |
| HTTP | axios | 1.8.2 | |
| 拖拽 | sortablejs | 1.13.0 | |
| 时间 | timeago.js | 4.0.2 | |
| 提及 | react-mentions | 4.3.1 | |

### 代码规模

| 语言 | 行数 | 文件数 |
|------|------|--------|
| Python | 29,181 | — |
| JS/JSX | — | 153(.js) + 71(.jsx) |
| TS/TSX | — | 33(.ts/.tsx) |
| React 组件 | — | 97 |

### 数据库

- PostgreSQL `mediacms_v7`（注意 skill 中也有写 `mediacms`，以 `local_settings.py` 为准）
- pgvector 扩展（embedding 向量搜索）

---

## CSS 四套体系混战（核心问题）

这是项目最大的技术债务源。

| 来源 | 文件数 | 位置 | 维护方式 |
|------|--------|------|----------|
| SCSS 源文件 | 55 | `frontend/src/static/css/` | webpack sass-loader 编译 |
| 编译产物 | 7+ | `frontend/dist/static/` → 复制到 `static/` | `npm run dist` 每次重写 |
| 手写静态 CSS | 15 | `static/css/` | 直接修改，不经过编译 |
| WAIC 主题 | 1 | `static/css/waic-theme.css` | 手写，含 `!important` 暴力覆盖 |

### 冲突机制

```
SCSS 变量 → 编译 → _commons.css (webpack产出)
                         ↓
              waic-theme.css 用 !important 硬覆盖
                         ↓
              个别模板注入 <style> 内联（终极覆盖）
```

三层打架，每层都用更高优先级压制上一层。成果脆弱——改 SCSS 变量不改 waic-theme.css 可能不生效，反之 `npm run dist` 后手写 CSS 如果被覆盖部分也可能丢失。

### AGENTS.md 中的 Tailwind 探索

AGENTS.md 里还有一份"赛博未来主义 UI 改造"任务指令，尝试引入 Tailwind CDN——这会变成**第四套** CSS 方案，进一步恶化问题。

---

## 技术债务清单

### P0 — CSS 归一化

**现状**: SCSS + 编译 CSS + 手写 CSS + waic-theme.css 四套共存
**影响**: 每次 UI 改动都可能在不同层打架，`!important` 泛滥
**方案A**: SCSS 全出，只用 CSS 变量 + 手写 CSS（改动小，waic-theme.css 不丢）
**方案B**: 全进 SCSS，waic-theme.css 改为 SCSS partial（改动大，但变量统一）

### P1 — React 版本分裂

**现状**: React 17.0.2（2020）配 TypeScript 5.9（2025）
**影响**: 
- `@types/react@19` 类型定义与新 React API 不匹配
- 缺少 `useId`、`useSyncExternalStore`、Concurrent Mode 等
- 33 个 TS 文件可能已有隐式类型错误
**方案**: 升到 React 18（保守）或 19（激进），需改 breaking changes

### P2 — 状态管理升级

**现状**: Flux 4.0.4 — Facebook 已停止维护
**影响**: 类组件 + Flux store 模式过时，新人难以维护
**方案**: 迁到 React Context + useReducer（零依赖）或 Zustand（轻量）

### P3 — TypeScript 覆盖率

**现状**: 257 个前端源文件仅 33 个用 TS（13%）
**影响**: 84% 代码无类型保护
**方案**: 渐进迁移，新组件写 TS，旧组件逐步加 `.d.ts`

### P4 — 管理后台视觉分裂

**现状**: Jazzmin + TinyMCE 独立于主站 SCSS/waic-theme.css
**影响**: admin 后台和主站看起来像两个产品
**方案**: Jazzmin 配色对齐 WAIC 蓝（改动小，改 settings.py 配置即可）

---

## 建议改造顺序

```
P0 CSS归一 → P1 React升级 → P2 Flux迁移 → P3 TS化 → P4 Admin统一
  (中)          (大)            (中)           (渐进)        (小)
```

P0 改完最立竿见影，后续改 CSS 不再有覆盖战。P1 是大手术但治本。
