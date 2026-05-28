# CSS 架构分析与统一方案

分析日期：2026-05-26

## CSS 加载顺序

```
1. _commons.css    ← SCSS编译产物（676KB），最先加载
2. _extra.css      ← 额外样式
3. waic-theme.css  ← EXTRA_CSS_PATHS 注入，最后加载 → 覆盖一切
```

加载链: `templates/common/head-links.html` → `_commons.css` → `_extra.css` → `EXTRA_CSS_PATHS`（含 `waic-theme.css`）

## SCSS 已桥接 CSS 变量

核心发现：SCSS 的 `_theme_variables.scss` 只有一行：

```scss
$theme-color: var(--theme-color, var(--default-theme-color));
```

这意味着所有 SCSS mixin（`font_color_gradient()` 等）编译后输出的都是 `color: var(--theme-color, var(--default-theme-color))`——本身就是 CSS 变量调用。

## 死代码分析：SCSS 主题变量文件

| 文件 | 内容 | 变量数 | 状态 |
|------|------|--------|------|
| `config/_light_theme.scss` | 亮色主题 CSS 变量定义（`body { --body-bg-color: #fafafa; ...}`) | 192个 | **死代码** |
| `config/_dark_theme.scss` | 暗色主题 CSS 变量定义（`body.dark_theme { --body-bg-color: #121212; ...}`) | 192个 | **死代码** |
| `config/index.scss` | 结构变量（`--header-height`, `--sidebar-width` 等）+ 默认品牌色 | ~20个 | 部分有用 |

**根因**: `_commons.css` 先加载，内部嵌入了 `_light_theme.scss` 的所有变量定义。然后 `waic-theme.css` 最后加载，用同名变量覆盖。SCSS 里 192 个变量值从未真正生效——始终被 waic-theme.css 覆盖。

## 为什么 waic-theme.css 需要 `!important`

waic-theme.css 里有 50+ 处 `!important`，不是因为 CSS 自身需要，而是为了覆盖 `_commons.css` 中的同名变量声明。一旦删除 SCSS 主题文件，`!important` 可以全部去掉。

## 变量覆盖链（以 sidebar-bg-color 为例）

```
SCSS 编译 → _commons.css 内嵌: --sidebar-bg-color: #f5f5f5   (亮色默认)
                                                   ↓ 被覆盖
waic-theme.css body:        --sidebar-bg-color: #1e3a5f      (WAIC 深海军蓝)
waic-theme.css .dark_theme: --sidebar-bg-color: #08090a      (暗色 Linear 黑)
```

## 统一方案

### 改什么

| 操作 | 文件 | 效果 |
|------|------|------|
| 删除 | `frontend/src/static/css/config/_light_theme.scss` | 移除 192 个死变量 |
| 删除 | `frontend/src/static/css/config/_dark_theme.scss` | 移除 192 个死变量 |
| 精简 | `frontend/src/static/css/config/index.scss` | 只保留结构变量 + 品牌色默认值 |
| 编译 | `npm run dist` | 生成新的 `_commons.css`（不再内嵌主题变量） |
| 去 `!important` | `waic-theme.css` | 删除 50+ 处不再需要的强制覆盖 |

### 不改的

- SCSS 组件规则（`.nav-menu`, `.popup`, 按钮样式等）——保留，这些是真正的结构 CSS
- `_theme_variables.scss` 的 `$theme-color` 桥接——保留，这是让 SCSS 编译输出 CSS 变量的关键
- `waic-theme.css` WAIC 品牌定制段——全部保留

### 收益

- CSS 变量源: 2套×每变量2值 → 1套
- `!important`: 50+ → 0
- `_commons.css`: 676KB → ~500KB
- 改主题色: 只需改 waic-theme.css 一处

## CSS 变量数量统计

| 文件 | CSS 变量引用数 | 说明 |
|------|---------------|------|
| `_light_theme.scss` | 192 | 死代码，可删 |
| `_dark_theme.scss` | 192 | 死代码，可删 |
| `_commons.css` (编译后) | ~220 | 内嵌了 _light_theme 变量 + normalize + 组件规则 |
| `waic-theme.css` | ~468 | 含 WAIC 自定义变量 + 注入 MediaCMS 变量 + 组件覆盖 |
