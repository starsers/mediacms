# WAIC 素材平台 — 技术架构全景

> 2026-05-24 分析

## 组件清单

| 层 | 技术 | 版本 | 角色 |
|---|---|---|---|
| 后端框架 | Django | 5.2.6 | ORM / REST / Admin / 模板 |
| API | Django REST Framework | 3.16 | REST API 端点 |
| 前端 | React | 19 | SPA (多入口页面) |
| 前端类型 | TypeScript | - | 编译时类型 |
| 构建工具 | Webpack (mediacms-scripts) | - | 自定义构建链 |
| 状态管理 | Flux | - | 前端状态 |
| 样式 | SCSS + PostCSS + Autoprefixer | - | 编译到 CSS |
| 模板引擎 | EJS | - | 前端模板 |
| 数据库 | PostgreSQL | psycopg 3.2 | 主存储 |
| 缓存/队列 | Redis | 6379/1 | Cache + Celery Broker |
| 异步任务 | Celery | 5.4 | 转码/字幕/AI分析 |
| WSGI | Gunicorn | 23 | 生产服务器 |
| 视频处理 | FFmpeg | - | 转码/降噪 |
| 语音识别 | openai-whisper | medium | 本地字幕生成 |
| AI分析 | DashScope (Qwen) | - | 图片/文档分析+嵌入 |
| 认证 | django-allauth + python3-saml | - | 本地+SAML SSO |
| Admin | django-jazzmin | 3.0 | 后台皮肤 |
| 富文本 | django-tinymce | 4.1 | 内容编辑 |
| 文件上传 | FineUploader (CDN) | 5.13 | 分片上传 |
| 错误监控 | Sentry | - | 生产错误追踪 |
| API文档 | drf-yasg | - | OpenAPI/Swagger |

## 架构判断：标准单体，非缝合怪

MediaCMS v8 本身就是成熟的 Django + React 单体应用。WAIC 加的功能（审批/水印/Word搜索/权限申请/分享弹窗/通知）全是 Django 应用层扩展，零新依赖。

## 当前部署方式（开发模式）

```
PostgreSQL ────┐
Redis ─────────┼──→ Django runserver :8005 ──→ 用户
Celery Worker ─┘   (--noreload, WSL /mnt/h/)
Celery Beat ───┘
```

5 个进程全手动管理，无 Docker/编排。

## 生产化打包方案

```
docker-compose.yml
├── postgres      (postgres:16-alpine)
├── redis         (redis:7-alpine)
├── web           (Django + Gunicorn, 同镜像)
├── celery_worker (同镜像，CMD: celery worker)
└── celery_beat   (同镜像，CMD: celery beat)
```

**缺失**：项目无 Dockerfile、无 docker-compose.yml、无 CI/CD。

## 进程启动命令（当前）

```bash
# Django
PYTHONUNBUFFERED=1 venv/bin/python manage.py runserver 0.0.0.0:8005 --noreload

# Celery Worker
DJANGO_SETTINGS_MODULE=cms.settings celery -A cms worker -Q long_tasks,short_tasks -l INFO --concurrency=2

# Celery Beat
DJANGO_SETTINGS_MODULE=cms.settings celery -A cms beat -l INFO
```

## 关键配置文件

| 文件 | 用途 |
|---|---|
| `requirements.txt` | Python 依赖 (27 packages) |
| `frontend/package.json` | Node 依赖 (mediacms-scripts + webpack生态) |
| `cms/settings.py` | Django 主配置 (668行) |
| `cms/local_settings.py` | 本地覆盖 (最后加载) |
| `cms/wsgi.py` | Gunicorn 入口 |

## 搜索数据库实现方案（面向后续多算法扩展）

### 目标

后续搜索不再只覆盖标题或基础全文，而是统一支持以下多种信息源的组合检索：

- 人脸特征检索
- 字幕 / 台词检索
- 视频标签检索
- 标题 / 描述 / AI 摘要检索
- 语义向量检索

目标不是为每一种搜索单独引入一套存储，而是继续以 **PostgreSQL 作为主搜索数据库**，在现有模型上分层扩展：

- 结构化过滤走普通字段 / 关联表
- 关键词召回走 PostgreSQL 全文检索
- 模糊匹配走 `pg_trgm`
- 语义召回走 `pgvector`
- 人脸相似度走独立向量表 + `pgvector`

这样可以在中期规模内保持部署简单、事务一致、开发成本低，同时给后续独立检索服务预留演进空间。

### 当前仓库已经具备的基础

现有代码里已经有一套可复用的搜索底座：

- `files.models.media.Media.search`：PostgreSQL `SearchVectorField`，用于全文检索
- `files.models.media.Media.embedding`：`pgvector` 向量字段，用于语义相似度搜索
- `files.models.media.Media.transcript_text`：存放转录字幕纯文本，可参与检索
- `files.models.media.Media.ai_summary` / `Media.ai_metadata`：可承载 AI 提取结果
- `files.models.category.Tag` 与 `Media.tags`：已具备标签维度检索能力
- `files.views.media.MediaSearch.get()`：已接入全文检索、中文兜底匹配、向量相似度排序

因此后续方案应以 **扩展现有 `Media` 聚合模型** 为主，而不是另起一套脱离仓库的数据模型。

### 推荐的数据库分层

#### 1. `media` 作为搜索聚合根

`media` 仍然是搜索结果的主实体，统一承接：

- 标题
- 描述
- 分类
- 作者
- 标签关联
- AI 摘要
- 转录摘要 / 聚合文本
- 通用语义 embedding

建议继续把“适合汇总后搜索”的文本同步到 `Media.search` 中，作为第一层通用召回入口。

#### 2. 字幕从“整段文本”升级到“分段可检索”

当前 `transcript_text` 更适合粗粒度召回；如果后续要稳定支持“搜到哪句就跳到哪句”，建议增加字幕分段表，例如：

- `media_id`
- `language`
- `start_seconds`
- `end_seconds`
- `content`
- `content_search` (`tsvector`)
- `embedding`（可选，给语义字幕检索用）

这样做的价值：

- 数据库内直接完成字幕命中，不必每次回退到文件解析
- 可以天然返回命中片段和时间戳
- 可以做字幕级排序，而不是只做媒体级排序
- 后续可支持“字幕关键词 + 媒体标签 + 时间片段”联合检索

#### 3. 人脸特征独立成高基数向量表

人脸不适合塞进 `media` 主表，建议单独建人脸特征表，例如：

- `id`
- `media_id`
- `face_vector` (`vector(N)`)
- `person_name`（可选，人工标注人物名）
- `source_type`（AI/人工/导入）
- `confidence`
- `start_seconds` / `end_seconds`（视频中出现时间，可选）
- `frame_no` / `image_path`（可选）
- `extra_metadata` (`jsonb`)

索引策略：

- `pgvector` HNSW / IVFFlat 索引建在 `face_vector`
- `media_id` 普通索引
- `person_name` 普通索引或 trigram 索引（如允许模糊搜人名）

这样可以支持：

- 以图搜人脸
- 人脸 + 标签联合筛选
- 人脸 + 字幕命中联合筛选
- 同一媒体多个面孔的独立召回与去重

#### 5. 标签与 AI 元数据继续保留“结构化 + 聚合搜索”双通道

标签、镜头分析、对象识别、OCR、章节、人物名、地点名等 AI 信息，建议采用两层存储：

- 可筛选、可统计的核心字段单独建列或关联表
- 原始分析结果保留在 `ai_metadata` / `jsonb`

其中：

- `Tag` 继续承接显式标签
- OCR 文本、章节标题、对象名、地点名等适合汇总到 `Media.search`
- 如果某一类信息以后需要单独排序或高亮，再拆为独立明细表

### 推荐插件与索引策略

#### 必备

- `pgvector`：文本 embedding、人脸 embedding
- PostgreSQL Full Text Search：标题、摘要、字幕、来源文本

#### 推荐补充

- `pg_trgm`：标题、人物名、来源名的模糊匹配
- 中文分词插件（如可用的中文分词方案）：用于替代当前 `simple` 配置对中文分词不佳的问题

#### 索引建议

- `Media.search`：GIN
- 字幕分段 `content_search`：GIN
- `Media.embedding`：HNSW
- 人脸 `face_vector`：HNSW（大规模）或 IVFFlat（中小规模）
- `source_platform` / `source_external_id` / `media_id`：BTREE
- 模糊搜索字段：GIN / GIST trigram

### 查询策略：统一做“多路召回 + 单路排序”

后续不要把所有条件都写成一条巨型 SQL 的固定模板，而应按搜索意图拆成多路召回，再汇总到 `media_id`：

1. **结构化过滤**：先按权限、媒体类型、分类、标签、来源平台等缩小候选集
2. **全文召回**：从标题、描述、AI 摘要、字幕、来源信息中召回
3. **向量召回**：对 query 文本 embedding 做语义相似度召回
4. **人脸召回**：对上传人脸向量做相似度召回
5. **结果归并**：按 `media_id` 去重，并保留各路命中证据
6. **统一排序**：组合文本分数、向量分数、人脸分数、业务权重

统一排序分数可抽象为：

`final_score = text_score * a + vector_score * b + face_score * c + business_score * d`

其中 `business_score` 可包含：

- 发布时间衰减
- 重要内容加权
- 人工精选加权
- 权限域内优先级

### 典型组合查询场景

#### 场景 1：字幕 + 标签

搜索“包含某句台词，并且标签属于某人物/栏目”的媒体。

#### 场景 2：人脸 + 字幕

搜索“人脸相似，并且字幕提到某关键词”的媒体。

#### 场景 3：来源 + 语义

搜索“来自某平台/某频道，并且内容语义接近某主题”的媒体。

#### 场景 4：人脸 + 标签 + 字幕

搜索“某人脸 + 某人物标签 + 某句台词”的交叉结果；数据库层先召回候选，再由应用层做归一化排序与高亮展示。

### 对当前仓库的落地顺序

#### 第一阶段：延续现状，增强聚合检索

在不大改模型的前提下，继续增强：

- `Media.search` 聚合内容来源
- `Media.embedding` 语义召回
- `Tag` / 分类 / 作者 / 时间过滤
- `transcript_text` 中文检索兜底

这是当前成本最低、兼容性最好的方案。

#### 第二阶段：补字幕明细表

当搜索结果需要稳定返回“命中字幕 + 精确时间点”时，新增字幕分段表，把当前基于文件解析的命中逻辑逐步迁到数据库层。

#### 第三阶段：补人脸特征表

当人脸搜索上线时，新增独立人脸向量表，不把多张脸直接塞进 `Media` 主表；搜索时以 `media_id` 汇总回主结果集。


#### 第五阶段：统一搜索服务层

在 Django 应用层新增统一搜索编排逻辑，负责：

- 多路召回
- 分数归一化
- 去重
- 高亮片段拼装
- 返回命中依据（命中字幕、命中标签、命中来源、人脸相似度等）

### 为什么这一方案适合本项目

这套方案适合当前仓库的原因是：

- 现有项目已经明确以 PostgreSQL 为主数据库
- 搜索代码已经接入全文检索和 pgvector，不需要推倒重来
- MediaCMS 的结果主实体天然就是 `Media`
- 标签、字幕、AI 摘要都可以围绕 `media_id` 汇总
- 人脸属于高基数、多向量子实体，拆表最符合后续扩展需求

结论上，后续即使加入更多搜索算法，数据库层仍建议坚持：

> **`Media` 作为统一结果实体，PostgreSQL 作为统一搜索底座，向量/字幕/标签/来源/人脸分别按最合适的粒度建模，再在应用层完成混合召回和排序。**

这样既能支撑当前中等规模的多维搜索，也不会过早把系统复杂度推到独立搜索集群级别。
