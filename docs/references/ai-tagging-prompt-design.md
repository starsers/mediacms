# AI 智能标签/分类 Prompt 工程设计

> 版本: 2026-05-20 | 文件: `files/ai_analysis.py`

## 架构: match-first 决策链

```
上传 → media_init() → ai_analyze_media.delay(token)
  → analyze_document() / analyze_image()
    → _get_existing_context()     ← 从 DB 取现有标签+分类
    → _build_tag_category_prompt() ← 构建统一 prompt
    → _call_qwen_text(prompt)      ← AI 决策
    → _auto_tag(media, data)       ← 应用标签（match/create/skip）
    → _auto_categorize(media)      ← 应用分类（match/suggest new）
```

## 核心函数

### `_get_existing_context()` — 获取上下文

从 DB 实时查询，AI 根据这些做匹配决策：

```python
# 标签: 取使用最多的 100 个
tags = Tag.objects.all().order_by('-media_count')[:100]
tag_names = [t.title for t in tags]

# 分类: 取所有全局分类
cats = Category.objects.filter(is_global=True)

# 返回: (tags_text, cats_text, tag_name_set, category_map)
```

### `_build_tag_category_prompt()` — 统一 Prompt 模板

所有分析器（文档/图片）共用此模板。关键设计：

```
你是一个中文内容分类助手。请分析以下{content_type}内容...

== 系统中已有的标签 ==    ← 从 DB 实时取
== 系统中已有的分类 ==    ← 从 DB 实时取
== 需要分析的内容 ==

返回 JSON:
- tags_to_apply:  从已有标签中挑选 2-5 个（名称完全一致）
- tags_to_create: 确实需要的新标签 1-3 个
- tags_to_skip:   AI 认为不够好的标签
- category_match: 已有分类名或 null
- category_suggestion: 建议新建的分类名
```

**规则层次**：
1. 优先匹配已有标签（避免同义词重复）
2. 找不到才新建（中文、简洁、3-6 字）
3. 模糊/过于宽泛的跳过（减少噪声）
4. 所有标签和分类名称必须使用中文

### `_auto_tag()` — 三层决策执行

```python
# 第1层: 匹配已有标签
for name in data['tags_to_apply']:
    tag = Tag.objects.filter(title=name).first()
    if tag: media.tags.add(tag)  # 不创建，直接用现有

# 第2层: 创建新标签
for name in data['tags_to_create']:
    tag, created = Tag.objects.get_or_create(title=name,
        defaults={'source': 'ai', 'user': media.user})
    # 新标签自动标 source='ai' + confidence 分数

# 第3层: 跳过（仅日志）
skipped = data['tags_to_skip']  # 不操作，只记日志
```

### `_auto_categorize()` — 匹配或新建

```python
if category_match:
    cat = Category.objects.filter(title=category_match).first()
    if cat:
        media.category.add(cat)      # 匹配到 → 直接加
        if cat.parent:
            media.category.add(cat.parent)  # 顺便加父分类
elif category_suggestion:
    cat, created = Category.objects.get_or_create(
        title=category_suggestion, defaults={'is_global': True})
    # 找不到匹配 → 新建分类
```

## 对比：旧方案 vs 新方案

| 维度 | 旧方案 | 新方案 |
|------|--------|--------|
| 标签来源 | AI 自由发挥 | 先看 DB 已有标签，匹配优先 |
| 分类来源 | 硬编码 5 大类树 | 从 DB 动态取所有分类 |
| 新建控制 | 无节制 get_or_create | AI 显式声明 tags_to_create |
| 质量控制 | 无跳过机制 | AI 可以跳过不够好的标签 |
| 分类扩展 | 改代码 | AI 自动建议新建分类 |
| 语言 | 英文 prompt + 英文输出 | 全中文 prompt + 强制中文输出 |
| prompt 位置 | 散落在各分析器中 | 统一 `_build_tag_category_prompt()` |

## 图片分析的差异

`analyze_image()` 使用 Qwen VL Plus（多模态），prompt 完全相同但额外要求：
- `description`: 图片场景描述
- `objects`: 可见物体列表
- `scene_type`: 场景类型枚举
- `dominant_colors`: 主色调

标签/分类部分与文档分析完全一致。

## 注意事项

- `analyze_media()` 不再单独调用 `_auto_categorize()`——每个分析器内部已完成
- `embed_media()` 改用真实标签 `media.tags.all()` 替代 `ai_metadata['ai_tags']`
- 删除的旧代码: `WAIC_CATEGORY_TREE`, `CATEGORY_FLAT_LIST`, `_ensure_waic_categories()`
