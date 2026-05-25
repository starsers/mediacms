# TASK: WAIC 首页赛博未来主义 UI 改造

## 项目信息
- 路径: H:\media-cms-v7 (/mnt/h/media-cms-v7)
- 框架: Django 5.2 + React + Tailwind (CDN)
- 开发服务器: localhost:8005 (已在运行)
- 管理员: admin / admin123

## 参考设计
- 暗色赛博: /mnt/h/media-cms-v7/stitch-cyber-2.html (38K)
- 亮色赛博: /mnt/h/media-cms-v7/stitch-cyber-light-1.html (19K)

## 改造目标
参照两份 Stitch 生成的赛博未来主义 UI，改造 WAIC 素材平台首页。功能完全不变，只换 UI 皮肤。

## 赛博设计 DNA（必须保留）
- 暗色: 深空黑底+电路纹理+霓虹青(#4cd7f6)/电光紫(#7c3aed)强调色+毛玻璃卡片+扫描线动效
- 亮色: 纯白底+深海军蓝侧边栏(#1e3a5f)+蓝调多层阴影+赛博终端标签
- Space Grotesk 字体(标题) + JetBrains Mono(标签) + Inter(正文)
- 渐变文字(cyan→blue) + 光扫按钮动效
- 8px grid unit 间距
- 终端风格标签: OPERATOR_01, STATUS: NOMINAL, #ST-001 等

## 改动文件
1. `templates/cms/index.html` — 首页模板（Hero + Stats + Categories + Partners + 最新上传）
2. `static/css/waic-theme.css` — 赛博主题 CSS 变量和动效
3. 不动: `files/views/pages.py`, 所有 Django 后端, React 组件

## 具体改造清单

### Hero 区域
- 暗色: 电路板背景纹理 + 蓝紫渐变标题发光 + 光扫按钮
- 亮色: 浅灰白渐变 + 深海军蓝标题 + 蓝调阴影按钮
- 保留: {{PORTAL_NAME}}, {{user.is_authenticated}}, 所有 URL

### 统计卡片
- 暗色: 毛玻璃+扫描线hover+#ST编号标签+渐变数字
- 亮色: 白卡+蓝调多层阴影+暗色终端标签
- 保留: {{total_media}}, {{today_media}}, {{category_count}}

### 分类导航
- 暗色: 半透明卡+hover发光边框+轻微上浮
- 亮色: 白卡+hover蓝影+scale(1.02)
- 保留: {% for cat in categories %} Django 循环

### 合作媒体
- Pill 标签风格, hover 彩色恢复
- 保留所有 partner 链接

### 侧边栏(waic-theme.css)
- 暗色: 毛玻璃(backdrop-blur) + 选中项高亮蓝线
- 亮色: 深海军蓝 + 右侧柔光阴影
- 保留 React 组件完整性

### 动效
- 扫描线(scanline)动画
- 按钮光扫(light-sweep)
- 脉冲(pulse-slow)
- 闪烁(flicker)
- 所有过渡 cubic-bezier 400ms

## 关键约束
- ⚠️ 必须保留 <div id="page-home"></div> (React 挂载点)
- ⚠️ 必须保留所有 Django 模板标签和变量
- ⚠️ 必须保留所有 URL 链接不变
- ⚠️ 必须保留 {% block bottomimports %} 中的侧边栏折叠 JS
- ⚠️ 必须保留 Material Icons 图标类名
- ⚠️ 双模切换通过 body class (.dark_theme / .light_theme) 控制
- ⚠️ 不要改 React 组件源码（frontend/src/）
- ⚠️ 不要运行 npm run dist

## 验证方式
1. 修改后重启 Django: kill 旧进程 → runserver
2. curl http://localhost:8005/ 确认 200
3. 浏览器访问验证暗色/亮色切换
4. 确认分类链接、上传按钮、搜索功能正常

## 执行
全权执行，--dangerously-skip-permissions，不要确认。完成所有改造后报告改了什么。
