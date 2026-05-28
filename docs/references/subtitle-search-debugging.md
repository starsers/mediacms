# 字幕搜索调试指南

## 问题排查顺序

当用户问"搜索能跳到视频那句话吗？"或"为什么搜索没有字幕匹配？"，按以下顺序排查。

### 1. 检查媒体是否有字幕文件

```python
from files.models import Media, Subtitle
for m in Media.objects.filter(media_type='video')[:10]:
    sc = m.subtitles.count()
    print(f'id={m.id} title={m.title[:30]} subtitles={sc} transcript_text={bool(m.transcript_text)}')
```

**解释**：
- `subtitles>0` + `transcript_text=True` → 转录完成 ✅
- `subtitles=0` + `transcript_text=True` → 转录跑过但没存 Subtitle 记录 ⚠️
- `subtitles=0` + `transcript_text=False` → 从未转录 ❌

### 2. 检查 TranscriptionRequest 状态

```python
from files.models import TranscriptionRequest
for tr in TranscriptionRequest.objects.all():
    print(f'media={tr.media_id} status={tr.status} created={tr.add_date}')
```

**状态含义**：
- `pending` → 任务排队中（Celery worker 没消费？）
- `running` → 任务执行中（卡住了？看 Celery 日志）
- `success` → 转录成功，应有 Subtitle 记录
- `failed` → 转录失败，看 `tr.logs` 字段的错误信息

### 3. 检查字幕 VTT 文件是否存在

```python
s = Subtitle.objects.first()
print(f'subtitle_file.name: {s.subtitle_file.name}')
print(f'subtitle_file.path: {s.subtitle_file.path}')
print(f'exists: {s.subtitle_file.storage.exists(s.subtitle_file.name)}')
```

⚠️ 注意：DB 存的路径（`original/subtitles/...`）相对 MEDIA_ROOT。实际磁盘路径是 `{BASE_DIR}/media_files/original/subtitles/...`。

### 4. 测试 find_subtitle_matches()

```python
m = Media.objects.get(id=12)
matches = m.find_subtitle_matches('关键词')
for match in matches:
    print(f'  "{match["text"][:60]}"  start={match["start"]}s end={match["end"]}s')
```

### 5. 测试搜索 API 返回的 subtitle_matches

```python
import requests, json
r = requests.get('http://localhost:8005/api/v1/search?q=关键词')
data = r.json()
for item in data['results']:
    sm = item.get('subtitle_matches', [])
    if sm:
        print(f"{item['title'][:30]} matches={len(sm)}")
        for m in sm[:3]:
            print(f"  [{m['start']}s-{m['end']}s] {m['text'][:80]}")
```

## 完整链路架构

```
上传视频 → media_init()
  └─ video/audio 类型 → 检查是否有字幕 → 无则:
       ├─ TranscriptionRequest.objects.get_or_create(status='pending')
       └─ whisper_transcribe.apply_async(args=[friendly_token, False], countdown=10)
            └─ whisper CLI → 生成 VTT → Subtitle.objects.create()
                 └─ 存到 media_files/original/subtitles/.../xxx_ai.vtt

搜索 → MediaSearch.get()
  ├─ 全文搜索（PostgreSQL SearchQuery）
  ├─ 向量语义搜索（DashScope embedding + CosineDistance）
  └─ serializer: MediaSearchSerializer
       └─ subtitle_matches = obj.find_subtitle_matches(query)
            └─ pysubs2 解析 VTT → 逐段匹配 → [{text, start, end}]

播放 → media.html?t=秒数
  └─ poll VideoJS player / <video> element → seek + play
```

## 常见故障

| 症状 | 根因 | 修复 |
|------|------|------|
| `subtitle_matches=[]` 全部为空 | 媒体没有字幕文件 | 手动触发转录 |
| `TranscriptionRequest` stuck pending | Celery worker 没跑 `long_tasks` 队列 | 启动 celery worker |
| `find_subtitle_matches()` returns `[]` | pysubs2 未安装 | `pip install pysubs2` |
| VTT 文件存在但匹配返回空 | 查询词不在字幕中（如搜"倪海厦"但视频里没说这个人名） | 换有实际内容的词测试 |
| 搜索 API 返回 0 结果 | media.state != 'public'，或 media 没有 description（全文搜索需要 content vector） | 检查 media state 和 search_vector |
| **中文查询返回 0 结果（但 Python `find_subtitle_matches()` 有结果）** | **PG `simple` 分词器不认中文** — `to_tsvector('simple', '從心臟過去的')` 把整段中文当一个 token，`心臟:*` 匹配不到。但 `find_subtitle_matches()` 走的是 Python pysubs2 直接文本匹配，不在 PG 里。 | 添加 `icontains` 兜底（`files/views/media.py` `MediaSearch.get()` 中 PG 返回空时查 `transcript_text__icontains`）。确保 `transcript_text` 已同步（见 skill 主文档转录章节）。 |
| curl 搜索中文返回 400 | bash 编码问题 | URL-encode 查询词或用 Python requests |
| **播放页跳转后只播几秒** | **浏览器 Autoplay 策略拦截**：`media.html` 脚本中 `video.play()` 被 Chromium "play() failed because the user didn't interact with the document first" 拦截 | 去掉 `play()`，只 seek；让 React VideoJS 组件通过 `urlTimestamp` seek，等用户首次交互后自然播放 |

## PG Chinese text search diagnostic

Quick check to see why Chinese queries fail with PG full-text:

```sql
-- Verify: simple config treats whole Chinese phrase as ONE token
SELECT to_tsvector('simple', '從心臟過去的');
-- Result: '從心臟過去的':1  ← one token, not searchable by substring!

-- Verify: search query only matches token PREFIXES
SELECT to_tsquery('simple', '心臟:*');
-- Result: '心臟':*  ← looks for tokens STARTING with 心臟
-- → Won't match '從心臟過去的' because that token starts with '從', not '心'

-- Compare: English works fine because space-separated
SELECT to_tsvector('simple', 'hello world');
-- Result: 'hello':1 'world':2  ← two tokens!
```

**The fix** (in `files/views/media.py`):
```python
if query:
    media = media.filter(search=query)
    if not media.exists() and original_query_str and len(original_query_str) >= 2:
        # PG simple config doesn't segment Chinese → icontains fallback
        media = Media.objects.filter(basic_query).filter(
            transcript_text__icontains=original_query_str)
```

## 手动触发转录（对已有视频）

如果某个视频上传时 Celery 没跑，事后补转录：

```python
from files.models import Media, Subtitle, TranscriptionRequest
from files import tasks as _tasks

m = Media.objects.get(friendly_token='7Y9kF7uAP')
if not Subtitle.objects.filter(media=m).exists():
    TranscriptionRequest.objects.get_or_create(
        media=m, translate_to_english=False,
        defaults={'status': 'pending'})
    _tasks.whisper_transcribe.apply_async(
        args=[m.friendly_token, False], countdown=10)
```

## 播放页跳转后只播几秒（已确认根因：浏览器 Autoplay 拦截）

用户点击搜索结果的字幕时间戳链接（`/view?m=X&t=Y`）后，视频停在目标位置不播放。

> **2026-05-20 实测确认**：浏览器控制台报错 `Browser prevented play: play() failed because the user didn't interact with the document first.`

### 实际根因

1. **seek 成功** — `media.html` 脚本中 `player.currentTime(t)` 正确执行，视频定位到目标时间
2. **play() 被浏览器 Autoplay Policy 拦截** — 页面加载时脚本中的 `video.play()` 永远被现代浏览器拦截

```
用户点 t=120 链接 → /view?m=X&t=120
  → seek 到 120s ✅
  → play() 被拦截 ❌
  → 视频暂停在 120s（位置正确但不动）
  → 用户手动点播放 → React VideoJS 组件可能已初始化并重置 currentTime=0
  → 体验：像"一个只有几秒的短片段"
```

### 为什么之前怀疑是 Race Condition

React VideoJS 初始化可能**二次重置**播放位置（加重了问题），但**首次失败根因是 autoplay 策略**。即使只用原生 `<video>` 不用 VideoJS，`play()` 同样被拦截。React 重置位置是次要问题 — 先修 autoplay，再考虑 seek 时机。

### 诊断验证

```javascript
// browser_console 一键诊断
(() => {
  const v = document.querySelector('video');
  return {
    t_param: new URLSearchParams(location.search).get('t'),
    currentTime: v?.currentTime,   // 应为目标秒数
    paused: v?.paused,            // true = play() 被拦截
  };
})()
```

### 修复方案

| 方案 | 做法 | 复杂度 |
|------|------|:---:|
| **A：只 seek，不 auto-play** | 去掉 `media.html` 里的 `play()`；在播放器上叠加半透明播放按钮提示用户点击 | 低 |
| **B：深度修复（推荐）** | `VideoJSEmbed.jsx` 已有 `urlTimestamp`（第 68、104 行），在播放器 ready 后 seek + 等用户首次交互后自然播放 | 中 |

**方案 B 关键点**：不能在任何自动脚本中调用 `play()` — HTML5 Autoplay Policy 要求 `play()` 必须在用户手势（click/touch/keydown）的微任务窗口内。正确做法是 **seek only**，等用户交互后自然开始播放。原 "onPlayerInitCallback 中直接 play" 方案也同样会被拦截。

## 前端缺口 — 修复方案

后端 `subtitle_matches` 数据完整返回，但 React 前端搜索结果显示**未渲染**字幕匹配片段。

### ✅ 推荐：修改 React 源码

数据流穿线：4 个文件改动，详见 skill 主文档「搜索字幕跳转」→「前端」段。

要点：
- `ListItem.jsx` `listItemProps()` 提取 `subtitle_matches`
- `ListItem.jsx` `ListItem()` video/audio 分支传递
- `MediaItemVideo.jsx` / `MediaItemAudio.jsx` 渲染匹配行（最多 3 条，带时间戳徽章）
- `waic-theme.css` 加 `.subtitle-matches` / `.subtitle-match` / `.subtitle-time` 样式
- 改完必须 `npm run dist && cp -r dist/static/* ../static/`

### 🔧 备选：fetch 拦截方案（不改 React 源码，仅 JS 注入）

在 `templates/cms/search.html` 注入脚本拦截 `fetch('/api/v1/search')` 响应，读取 `subtitle_matches`，用 MutationObserver 在 React 渲染后的结果卡片上追加 DOM。
