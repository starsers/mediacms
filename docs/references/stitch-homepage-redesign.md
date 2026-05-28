# Stitch AI 首页重设计 → Claude Code 落地工作流

## 完整流程（5步）

### 1. 准备：启动项目 + 截图
```bash
# 启动 Django
cd /mnt/h/media-cms-v7
./venv/bin/python manage.py runserver 0.0.0.0:8005 --noreload &

# 启动 Chrome CDP + 截图
# browser_navigate → http://localhost:8005/ → browser_vision
```

### 2. Stitch 生成暗色版
```python
# generate_screen_from_text
args = {
    'projectId': '17239077371614721644',  # 纯数字，无前缀
    'prompt': '详细的赛博未来主义设计提示词...',
    'modelId': 'GEMINI_3_1_PRO'  # 可选，默认也可以
}
```

### 3. 提取 HTML + 生成亮色版
```python
# get_screen → structuredContent.htmlCode.downloadUrl → 下载
# generate_screen_from_text 再生成亮色版（不要用 edit_screens/edit_variants）
```

### 4. AGENTS.md 任务简报
必须包含：
- 项目路径、端口
- 参考设计文件路径
- 改动文件（templates/cms/index.html + static/css/waic-theme.css）
- 不改的（React 源码、后端）
- 关键约束：`<div id="page-home">`、Django 模板标签、URL、侧边栏折叠 JS
- 设计 DNA：颜色映射、字体、动效、间距

### 5. 执行（二选一）
- **delegate_task**（推荐，WSL→Windows Claude Code 管道不可靠）
- Claude Code CLI（如果管道通的）

## 提示词工程要点

### 好的提示词必须包含
1. **设计人格**: "赛博未来主义"、"虚空/水晶宫"——给风格命名
2. **精确颜色**: 亮暗模式每个元素的颜色映射（bg、card、text、border、shadow）
3. **具体动效**: 扫描线(scanline)、光扫(light-sweep)、脉冲(pulse-slow)、闪烁(flicker)
4. **字体方案**: 标题(Space Grotesk)、标签(JetBrains Mono)、正文(Inter)
5. **间距系统**: 4px/8px base unit
6. **参考截图**: 提到项目中有截图可用

### 糟糕的提示词
- "设计一个好看的首页"（太模糊）
- "用 Tailwind + Material"（只有技术栈，无设计方向）
- 只描述布局不描述氛围和感觉

## 坚哥的风格偏好
- 喜欢赛博朋克/科幻未来感（"冷冽、未来、科技酷感"）
- 拒绝"幼稚、土气"的设计
- 要求亮暗双模有"巨大反差"
- 暗色要"真黑"（#08090a），不是深灰
- 亮色要苹果/Stripe 级别的干净
