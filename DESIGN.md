---
version: alpha
name: WAIC-MediaCMS
description: 世界人工智能大会内部素材分享平台 — 深蓝科技感 × 极简白底 × 卡片式媒体展示
colors:
  primary: "#1e293b"
  secondary: "#64748b"
  tertiary: "#1a56db"
  accent: "#0ea5e9"
  neutral: "#f1f5f9"
  on-primary: "#ffffff"
  on-tertiary: "#ffffff"
  sidebar-bg: "#1e40af"
  sidebar-gradient-end: "#1a56db"
  success: "#10b981"
  card-border: "#dbeafe"
  card-hover-border: "#1a56db"
typography:
  h1:
    fontFamily: Inter
    fontSize: 2rem
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  h2:
    fontFamily: Inter
    fontSize: 1.5rem
    fontWeight: 600
    lineHeight: 1.25
  h3:
    fontFamily: Inter
    fontSize: 1.25rem
    fontWeight: 600
    lineHeight: 1.3
  body-md:
    fontFamily: Inter
    fontSize: 0.938rem
    lineHeight: 1.5
  body-sm:
    fontFamily: Inter
    fontSize: 0.813rem
    lineHeight: 1.43
  nav-label:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: 500
    letterSpacing: "0.02em"
  btn-text:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: 600
rounded:
  sm: 6px
  md: 10px
  lg: 16px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  "2xl": 48px
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
    rounded: "{rounded.sm}"
    padding: 10px
  button-primary-hover:
    backgroundColor: "{colors.sidebar-bg}"
    textColor: "{colors.on-tertiary}"
  card:
    backgroundColor: "{colors.on-primary}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: 16px
  sidebar:
    backgroundColor: "{colors.sidebar-bg}"
    textColor: "{colors.on-primary}"
  media-player:
    backgroundColor: "#0f172a"
    textColor: "{colors.on-primary}"
---

## Overview

WAIC 素材平台 — 为世界人工智能大会内部设计的媒体素材分享系统。
视觉感受：专业、科技感、可信赖。第一印象：这是属于 AI 大会的专属
平台，不是通用视频网站。深蓝侧边栏如会议主视觉的延伸，白色卡片区
干净利落，蓝色交互元素精准高效。

## Colors

- **Primary (#1e293b):** 主文字色。深蓝灰，比纯黑柔和，有科技温度。
- **Secondary (#64748b):** 辅助文字。描述性文本、元数据。
- **Tertiary (#1a56db):** 交互主色。按钮、链接、选中态。大会蓝。
- **Accent (#0ea5e9):** 强调色。播放按钮、活跃指示、hover 高亮。只用在小面积。
- **Neutral (#f1f5f9):** 页面背景。浅蓝灰，比纯白有层次。
- **Sidebar (#1e40af → #1a56db):** 侧边栏渐变。深蓝到大会蓝，品牌锚点。
- **Success (#10b981):** 成功色。转码完成、上传成功。
- **Card Border (#dbeafe):** 卡片浅蓝边框，hover 时变为 Tertiary。

## Typography

系统字体栈 `Inter, system-ui, -apple-system, sans-serif`。
中文字体回退到系统默认。层次通过字重和大小区分：700=标题，600=按钮/强调，400=正文。
正文 15px 保证中文可读性。

## Layout

左侧边栏（240px）+ 右侧内容区。卡片网格：桌面 3 列 → 平板 2 列 → 手机 1 列。
卡片间距 16px，区块间距 32px。

## Shapes

圆角：交互元素 6px（按钮、输入框），卡片 10px（略圆润显现代），
头像和标签 9999px 全圆角。

## Components

- `button-primary`: 页面唯一高强调按钮色。蓝色底白色字。
- `card`: 素材卡片。白色底浅蓝边框，hover 边框变深蓝。
- `sidebar`: 深蓝渐变背景，白色文字图标。
- `media-player`: 深色背景，适合视频播放沉浸感。

## Do's and Don'ts

- **Do** 用 token 引用 `{colors.tertiary}` 而非硬编码 hex。
- **Do** 保持侧边栏深蓝渐变 — 这是品牌锚点。
- **Do** 素材卡片用浅蓝边框 hover — 细微但有效的交互反馈。
- **Don't** 在正文用纯黑 `#000` — 用 `{colors.primary}`。
- **Don't** 滥用 Accent `#0ea5e9` — 它是信号色，不是装饰色。
- **Don't** 引入暖色（橙、红、黄）进入主界面。
