# MediaCMS 多语言混搭完整修复方案

## 问题表现
页面中英文混搭：模板 Django `{% trans %}` 中文正常，但 React 组件大量英文，侧边栏 navItems 显示 "About"/"Terms"/"Contact"，搜索框 placeholder 是英文。

## 根因（4层）

| # | 层次 | 根因 | 文件 |
|:--|:--|:--|:--|
| ① | 中间件 | `LocaleMiddleware` 激活，浏览器 `Accept-Language: en` 优先于 `LANGUAGE_CODE` | `settings.py:315` |
| ② | 模板 | `<html lang="en">` 写死 | `templates/root.html:3` |
| ③ | 翻译 | `zh_hans.py` 298 条中约 128 条值为空 → React 回退显示英文 key | `files/frontend_translations/zh_hans.py` |
| ④ | 配置 | `contents.html` 侧边栏 navItems "About"/"Terms"/"Contact" 硬编码英文 | `templates/config/installation/contents.html` |

## 修复顺序（按依赖关系）

### 1. 补全翻译文件
`files/frontend_translations/zh_hans.py` — 所有空值 `""` 填上中文翻译。128 条需补全，包括：
- 权限管理相关："Add / Remove Co-Editors" → "添加/移除 协作编辑者"
- 操作按钮："Cancel" → "取消", "Confirm" → "确认"
- 状态提示："Failed to fetch..." → "获取...失败"
- 批量操作：全部翻译

### 2. 修复 HTML lang 属性
`templates/root.html` 第 3 行：
```html
<!-- 修改前 -->
<html lang="en">
<!-- 修改后 -->
<html lang="zh-hans">
```
**不要用** `{{ LANGUAGE_CODE }}` 模板变量——`request.LANGUAGE_CODE` 不在模板上下文中。

### 3. 侧边栏导航中文化
`templates/config/installation/contents.html` 的 `sidebar.navMenuItems`:
```javascript
// 修改前
{ text: "About", link: "/about", icon: 'contact_support' }
{ text: "Terms", link: "/tos", icon: 'insert_drive_file' }
{ text: "Contact", link: "/contact", icon: 'alternate_email' }
// 修改后
{ text: "关于", link: "/about", icon: 'contact_support' }
{ text: "条款", link: "/tos", icon: 'insert_drive_file' }
{ text: "联系", link: "/contact", icon: 'alternate_email' }
```

### 4. 限制语言列表（关键！）
`cms/local_settings.py` 中重写 `LANGUAGES`，只保留中文：
```python
LANGUAGE_CODE = "zh-hans"
LANGUAGES = [
    ('zh-hans', 'Simplified Chinese'),
]
```
**LocaleMiddleware 保留不动！** 限制 `LANGUAGES` 后，浏览器 `Accept-Language: en` 不在允许列表 → Django 回退到 `LANGUAGE_CODE = "zh-hans"`。

### 5. 重建前端
翻译键修改必须编译：
```bash
cd /mnt/h/media-cms-v7/frontend && npm --prefix . run dist
cp -r /mnt/h/media-cms-v7/frontend/dist/static/* /mnt/h/media-cms-v7/static/
```

## 试过的错误方案

### ❌ 移除 LocaleMiddleware
在 `settings.py` 中注释掉 `LocaleMiddleware` → 模板中 `{% get_current_language as LANGUAGE_CODE %}` 报 500 错误：
```
AttributeError: 'WSGIRequest' object has no attribute 'LANGUAGE_CODE'
```
因为 `request.LANGUAGE_CODE` 由 `LocaleMiddleware` 设置，移除后模板标签拿不到语言。

### ❌ 在 local_settings.py 中操作 MIDDLEWARE
`local_settings.py` 由 `settings.py` 通过 `from .local_settings import *` 导入。Python 的 `from X import *` 不共享 X 的命名空间给被导入模块。所以 `local_settings.py` 中 `MIDDLEWARE.remove(...)` 会报 `NameError: name 'MIDDLEWARE' is not defined`。
**正确做法**：直接改 `settings.py` 的 MIDDLEWARE 列表，或重新赋整个变量。

## 验证清单
- [ ] `curl -s http://localhost:8005/ | grep 'lang='` → `zh-hans`
- [ ] 浏览器开首页，检查搜索框 placeholder → `搜索素材、分类、标签…`
- [ ] 侧边栏导航 → 全中文（主页/精选/推荐/最新/标签/分类/在线剪辑/关于/条款/联系）
- [ ] 登录/注册按钮 → 中文
- [ ] 搜索页 Filter 侧栏 → 中文
