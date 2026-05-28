# 分享弹窗专业审查 (2026-05-21)

## 审查范围

MediaCMS v8.0.9 素材详情页分享弹窗，以专业 UX/工程角度审查。

## 组件架构

```
MediaShareOptions.jsx  ← 主弹窗组件
├── shareOptionsList()  ← 从 ShareOptionsContext 读取社交平台列表
│   └── switch: 'embed' (仅video/audio) / 'email' (mailto:)
│   └── 其余10个平台 → else 分支，期望 shareUrl 但从未填充 → 空 div
├── ShareOptions()      ← 渲染社交分享按钮（Email / Embed）
├── copy-field          ← 链接输入框 + COPY 按钮 → onClickCopyMediaLink()
├── share-popup-title   ← "分享素材" + X 关闭按钮
├── share-hint          ← "复制链接发送到微信或飞书"
└── start-at            ← 视频时间戳 checkbox
```

**弹窗 DOM 结构**: `.popup > .popup-fullscreen > .popup-main > .scrollable-content`

**PopupContent 关闭机制**: 监听 `mousedown`（overlay 点击）和 `keydown`（ESC），通过 `useImperativeHandle` 暴露 `hide()`。

## 🔴 Bug 级

### 1. "Start at NaN:NaN" — 非视频媒体

**位置**: `MediaShareOptions.jsx` Line 207-209, 261

```js
const localTimestamp = getTimestamp();  // document.getElementsByTagName("video")[0]?.currentTime
setTimestamp(localTimestamp);           // undefined for images/docs
setFormattedTimestamp(ToHHMMSS(localTimestamp));  // "NaN:NaN"
```

**根因**: `getTimestamp()` 从 `<video>` 元素读取 `currentTime`。图片/文档页面没有 video 元素 → `undefined` → `ToHHMMSS(undefined)` = `"NaN:NaN"`。

**修复**: 非 video/audio 媒体隐藏 start-at checkbox：
```jsx
{['video', 'audio'].includes(MediaPageStore.get('media-data').media_type) && (
  <div className="start-at">...</div>
)}
```

### 2. `updateShareMediaLink` 逻辑反了 + 使用过期 state

**位置**: Line 171-180

```js
function updateStartAtCheckbox() {
  setStartAtSelected(!startAtSelected);  // React setState 异步！
  updateShareMediaLink();                // 读到的是旧值
}

function updateShareMediaLink() {
  const newLink = startAtSelected ? mediaUrl : mediaUrl + "&t=" + ...;  // 逻辑反了！
  setShareMediaLink(newLink);
}
```

**两个 bug 叠加**：
1. **逻辑反转**: `startAtSelected=true`（勾选）时应加 `&t=`，当前代码反着来
2. **stale state**: `setStartAtSelected` 是异步的，`updateShareMediaLink()` 立即执行时读到旧值

**修复**: 直接用新值计算，不依赖异步 state：
```js
function updateStartAtCheckbox() {
  const newStartAtSelected = !startAtSelected;
  setStartAtSelected(newStartAtSelected);
  setShareMediaLink(newStartAtSelected ? mediaUrl + "&t=" + Math.trunc(timestamp) : mediaUrl);
}
```

## 🟡 UX 问题

### 3. Email 按钮位置不当

信息流：提示"微信/飞书" → **Email 按钮**（mailto:） → 复制框

WAIC 是内部文件分享平台，用户通过微信/飞书复制链接。Email 按钮打开邮件客户端，与上下文完全脱节。

**建议**: 移除 Email 按钮，或移到不显眼位置。

### 4. 社交分享平台大面积死代码

`ShareOptionsContext` 配置了 12 个平台：
```
['embed', 'fb', 'tw', 'whatsapp', 'telegram', 'reddit', 'tumblr', 'vk', 'pinterest', 'mix', 'linkedin', 'email']
```

但 `shareOptionsList()` 的 switch 只处理 `'embed'` 和 `'email'`。其余 10 个平台走 else 分支期望 `shareOptions[k].shareUrl`，但从未被填充 → 渲染空 `<div>`。

影响：items 计数错误、slider 逻辑误判、无意义的数组遍历。

### 5. 复制反馈是全局通知

COPY 后通过 `MediaPageActions.copyShareLink` → dispatcher → `onCompleteCopyMediaLink` → `PageActions.addNotification` 全局通知。页面滚动时可能被挡住。

**建议**: 按钮内联反馈（"已复制 ✓" 持续 2 秒）。

## 🟢 Close 按钮实现细节

`PopupContent` 不暴露 `close()` 方法给子组件。关闭按钮通过 dispatch ESC KeyboardEvent 触发 PopupContent 自身的 keydown handler：

```jsx
onClick={() => {
  document.dispatchEvent(new KeyboardEvent('keydown', {
    keyCode: 27, which: 27, bubbles: true
  }));
}}
```

CSS: `.share-popup-title { position: relative; }` + `.share-close-btn { position: absolute; right: 0; }`
