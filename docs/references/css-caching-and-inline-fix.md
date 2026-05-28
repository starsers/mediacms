# CSS 缓存顽固 + 内联注入 + 多位置同步

## 问题

修改 `static/css/waic-theme.css` 后，浏览器完全不加载新 CSS。即使：
- 清除浏览器全部数据（Chrome Settings → 删除浏览数据）
- 用 `?v=N` 参数
- 用 Network.setCacheDisabled CDP
- Django 重启

`document.styleSheets[i].cssRules.length` 永远是旧值。根因：CSS 的 `?v=8.0.9` cache buster 不变，浏览器顽固缓存。

服务端 `curl` 确认文件已更新，但 browser 端始终旧版。

## 终极方案：template 内联 `<style>`

在 `templates/root.html` 的 `<head>` 中加 `<style>` 块，位于 `{% include "config/index.html" %}` 之后：

```html
<style>
    :root, body {
        --default-item-width: 210px !important;
        --item-width: 210px !important;
    }
    .item.tag-item { width: 210px !important; max-width: 210px !important; }
    .sidebar-theme-switcher { margin: 2px 12px !important; padding: 3px 8px !important; max-height: 32px !important; }
    .page-header-right .circle-icon-button img { width: 40px !important; height: 40px !important; border-radius: 50% !important; object-fit: cover !important; }
</style>
```

改完重启 Django（需要重启因为模板变化）。

## 静态文件三位置同步

每次修改 `static/` 下文件后：

```bash
SRC=/mnt/h/media-cms-v7/static/css/waic-theme.css
cp $SRC /mnt/h/media-cms-v7/static_collected/css/waic-theme.css
cp $SRC /mnt/h/media-cms-v7/frontend/dist/static/css/waic-theme.css
```

三个路径：
- `static/` — 开发时 Django serve 的主目录
- `static_collected/` — collectstatic 目标
- `frontend/dist/static/` — npm dist 编译产物

## 编辑器 CSS 修改同步

编辑器文件在 `static/jianshen/` 下，同样需同步：

```bash
cp /mnt/h/media-cms-v7/static/jianshen/assets/css/index-*.css /mnt/h/media-cms-v7/static_collected/jianshen/assets/css/
cp /mnt/h/media-cms-v7/static/jianshen/assets/js/index-*.js /mnt/h/media-cms-v7/static_collected/jianshen/assets/js/
```

## 验证方法

```bash
# 服务端确认
curl -s "http://localhost:8005/static/css/waic-theme.css" | grep "max-height: 32px"

# 模板确认
curl -s http://localhost:8005/ | grep "default-item-width"
```

## 素材卡片宽度

`--default-item-width` CSS 变量控制列表项宽度。`_commons.css` 默认 218px，WAIC 配置可能覆盖为 342px。

browser_console 验证当前值：
```javascript
getComputedStyle(document.body).getPropertyValue('--default-item-width').trim()
```
