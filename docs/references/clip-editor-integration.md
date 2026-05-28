# Clip Editor Integration — 素材一键发送到简神编辑器

## 目标
左侧素材库点"📤 编辑" → 素材自动加载到简神编辑器的本地素材区、时间线、播放器，全程自动化。

## 完整链路（4步）
```
点"📤 编辑" (clip.html)
  → sendToEditor() — fetch 详情 API 获取 original_media_url
  → postMessage({action:'loadMedia', url, title}) → iframe 注入脚本
  → 注入脚本: fetch blob → DragEvent('drop') → 编辑器导入素材
  → 等600ms → 自动双击素材卡片 → 进时间线+播放器
  → 轮询 video.readyState → 就绪后隐藏"加载中"
```

## 注入脚本（完整增强版）

```javascript
(function() {
    if (window.__mediaLoaderInjected) return;
    window.__mediaLoaderInjected = true;

    function dblclickEl(el) {
        const rect = el.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const opts = { bubbles: true, cancelable: true, clientX: cx, clientY: cy };
        el.dispatchEvent(new MouseEvent('mousedown', opts));
        el.dispatchEvent(new MouseEvent('mouseup', opts));
        el.dispatchEvent(new MouseEvent('click', opts));
        el.dispatchEvent(new MouseEvent('mousedown', opts));
        el.dispatchEvent(new MouseEvent('mouseup', opts));
        el.dispatchEvent(new MouseEvent('click', opts));
        el.dispatchEvent(new MouseEvent('dblclick', opts));
    }

    function hideLoading() {
        document.querySelectorAll('h4').forEach(function(h) {
            if (h.textContent.trim() === '加载中') h.style.display = 'none';
        });
    }

    function waitForVideoThenHide() {
        var attempts = 0;
        var timer = setInterval(function() {
            attempts++;
            var video = document.querySelector('video');
            if (video && video.readyState >= 2) {
                clearInterval(timer);
                hideLoading();
            } else if (attempts > 30) {  // 6秒兜底
                clearInterval(timer);
                hideLoading();
            }
        }, 200);
    }

    window.addEventListener('message', async function(ev) {
        if (!ev.data || ev.data.action !== 'loadMedia' || !ev.data.url) return;
        var title = ev.data.title || 'media';
        try {
            var resp = await fetch(ev.data.url);
            var blob = await resp.blob();
            var ext = title.split('.').pop() || 'mp4';
            var mimeMap = {mp4:'video/mp4',webm:'video/webm',mp3:'audio/mpeg',
                           wav:'audio/wav',jpg:'image/jpeg',png:'image/png',
                           gif:'image/gif',pdf:'application/pdf'};
            var mime = mimeMap[ext] || blob.type || 'application/octet-stream';
            var file = new File([blob], title, {type: mime});

            // 1. Drop into editor
            var dt = new DataTransfer();
            dt.items.add(file);
            var dropEv = new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true});
            document.dispatchEvent(dropEv);
            var zones = document.querySelectorAll('[class*="drop"],[class*="upload"],[class*="drag"],[class*="import"]');
            zones.forEach(function(z) { z.dispatchEvent(dropEv); });

            // 2. 等编辑器处理完导入
            await new Promise(function(r) { setTimeout(r, 600); });

            // 3. 找对应素材卡片并双击加载到播放器
            var items = document.querySelectorAll('.import-media-item');
            var found = false;
            for (var i = 0; i < items.length; i++) {
                var t = items[i].querySelector('.import-media-item-title');
                if (t && t.textContent.trim() === title) {
                    dblclickEl(items[i]);
                    found = true;
                    waitForVideoThenHide();
                    break;
                }
            }
            // 兜底：不支持的文件格式（编辑器不创建素材卡片）
            if (!found) {
                setTimeout(hideLoading, 2000);
            }
        } catch(e) {
            console.warn('MediaLoader: failed', ev.data.url, e);
            setTimeout(hideLoading, 2000);
        }
    });
})();
```

## 父页面 sendToEditor（clip.html）

```javascript
async function sendToEditor(url, title, type) {
    const iframe = document.getElementById('clip-editor');
    if (!iframe?.contentWindow) return showToast('编辑器未加载');

    let apiUrl = url;
    if (url.includes('/view?m=')) {
        const token = url.split('view?m=')[1].split('&')[0];
        apiUrl = API_BASE + '/media/' + token;
    }

    showToast('正在获取文件...');
    const resp = await fetch(apiUrl, {credentials:'same-origin'});
    const data = await resp.json();
    const fileUrl = data.original_media_url;
    if (!fileUrl) return showToast('无法获取文件地址');

    iframe.contentWindow.postMessage({
        action: 'loadMedia', url: fileUrl, title: data.title || title, type: type
    }, '*');
    showToast('已发送到编辑器');
}
```

## 关键技术点

### 为什么需要 fetch 详情 API？
搜索/列表 API 不返回 `original_media_url`。只有详情 API (`/api/v1/media/TOKEN`) 才返回文件直链。

### 为什么用 DragEvent 而非直接调用编辑器 API？
简神是编译好的 Vue 3 应用，无源码可改。但它监听了原生 DOM drop 事件。构造 `DragEvent` + `DataTransfer` + `File` 可欺骗编辑器。

### 为什么自动双击？
编辑器收到 drop 后只把素材加入"本地素材"库，不会自动加载到播放器。需要双击素材卡片才会进时间线+播放器。

### "加载中"隐藏策略
播放器初始显示 `<h4>加载中</h4>`。video 元素创建后需等 `readyState >= 2`。用 200ms 轮询，最多 30 次（6 秒），超时也强制隐藏。

### 不支持格式兜底
图片进库但不需要进播放器（正常行为）。文档（txt/docx/pdf）编辑器完全不支持，素材卡片不会出现 → `found=false` → 2 秒后强制隐藏"加载中"。catch 异常也走同样兜底。

## 兼容性测试结果

| 素材类型 | 大小 | 进库 | 进播放器 | "加载中"隐藏 | 备注 |
|---------|------|------|---------|------------|------|
| 小视频 mp4 | 0.1MB | ✅ | ✅ | ✅ | 10s, readyState=4 |
| 大视频 mp4 | 113.9MB | ✅ | ✅ | ✅ | 30min, 853px |
| 字幕视频 mp4 | 105.4MB | ✅ | ✅ | ✅ | 32min |
| 图片 jpg | — | ✅ | — | ✅ | 不进播放器是正常行为 |
| 文档 txt | — | ❌ | — | ✅ 2s兜底 | 编辑器不支持 |

## 为什么用 programmatic DragEvent？
简神是编译好的 Vue 应用，无法修改源码添加 postMessage 监听。但它的 drop handler 监听了原生 DOM 的 drop 事件。通过构造 `DragEvent` + `DataTransfer` + `File`，可以欺骗编辑器以为用户拖了一个文件进来。

## 同源限制
iframe URL 是 `/clip/editor/`，父页面是 `/clip/`，同源 → `contentWindow` 可访问 → 可以注入脚本。
