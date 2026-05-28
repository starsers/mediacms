# 上传页设计评审清单（v2 Premium）

## 当前评分：9.5/10（入场动画 + 格式提示 + 浮动图标 + 精致阴影）

## 已完成的 6 项改造

| # | 问题 | 修复方式 | 效果 |
|---|------|---------|------|
| 1 | "或"分隔线太细太淡 | 1.5px 渐变线 + 深色字 `#8090a8` + 字母间距 | 视觉存在感翻倍 |
| 2 | 拖拽区缺"灵动感" | `scale(1.008)` hover + `scale(1.012)` drag-over + glow box-shadow | 活起来了 |
| 3 | 按钮缺精致感 | 双层 box-shadow（小阴影+大阴影）+ `translateY(-2px)` hover | 有"贵感" |
| 4 | 云图标太透 | opacity 0.45→0.55, hover→0.75 + `waicIconFloat` 浮动动画 | 像呼吸一样 |
| 5 | 缺格式提示 | 一行圆角 pills（MP4/AVI/MOV/MP3/PDF/DOCX...）| 用户不用猜 |
| 6 | 缺入场动画 | `waicFadeInUp` 动画，逐层延迟（wrap→zone→btn→pills）| 页面"点亮"起来 |

## 关键 CSS 模式

### 入场动画链（staggered）
```css
.media-uploader-wrap          { animation: waicFadeInUp 0.6s ease-out; }
.waic-drag-drop-zone           { animation: waicFadeInUp 0.6s ease-out 0.1s both; }
.waic-upload-buttons           { animation: waicFadeInUp 0.5s ease-out 0.2s both; }
.waic-upload-formats           { animation: waicFadeInUp 0.5s ease-out 0.3s both; }
```
`both` fill-mode 确保元素在动画开始前保持透明。

### 图标浮动动画
```css
@keyframes waicIconFloat {
    0%, 100% { transform: translateY(0); }
    50%      { transform: translateY(-6px); }
}
/* 只在 hover 时触发，避免干扰 */
.waic-drag-drop-zone:hover .material-icons {
    animation: waicIconFloat 2s ease-in-out infinite;
}
```

### 双层阴影公式
```css
box-shadow: 0 2px 4px rgba(c,0.2),   /* 近距离紧凑阴影 → 立体感 */
            0 4px 12px rgba(c,0.15); /* 远距离扩散阴影 → 浮起感 */
```

### 格式 Pills HTML
```html
<div class="waic-upload-formats">
    <span class="waic-format-pill">MP4</span>
    <span class="waic-format-pill">PDF</span>
    ...
</div>
```
CSS: `padding: 3px 10px; border-radius: 20px; background: #f1f5fb; font-size: 0.7rem;`

## ⚠️ 踩坑记录

1. **CSS 缓存顽固**: 修改 `_commons.css` 后浏览器可能缓存旧版，用 CDP `Network.clearBrowserCache` 或版本参数绕过
2. **模板 vs React**: 上传页是 Django 模板，不是 React 组件，改模板后 `npm run dist` 不会生效，直接重启 Django
3. **FineUploader CSS 冲突**: 原生 `.browse-files-btn-wrap` 和 `.qq-upload-button-selector` 直接子元素会覆盖自定义按钮样式，需 `display:none` 隐藏
4. **webkitdirectory 跨浏览器**: `webkitdirectory` 只支持 Chrome/Edge，Firefox 不支持文件夹选择
