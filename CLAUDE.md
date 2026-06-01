AGENTS.md

## 文档功能测试方法（Docker）

### 适用场景

- 验证 `document/pdf` 类型是否能在运行态正常展示
- 验证搜索/管理/个人页筛选里是否出现 `Document`
- 验证文档详情页是否仍走非视频下载入口

### 启动开发环境

```bash
docker compose -f docker-compose-dev.yaml up -d
```

默认访问地址：

- Django: `http://localhost:8089`
- Frontend dev server: `http://localhost:8088`
- 管理员账号: `admin / admin`

### 创建最小文档样本

当数据库里没有现成 `document/pdf` 记录时，在容器中创建一个公开 txt 文档样本：

```bash
docker compose -f docker-compose-dev.yaml exec -T web python manage.py shell -c "from django.core.files.base import ContentFile; from users.models import User; from files.models import Media; user=User.objects.get(username='admin'); media=Media.objects.create(user=user,title='Verification Document',description='runtime verification sample',media_file=ContentFile(b'hello document verification', name='verification-document.txt'), state='public', listable=True, is_reviewed=True); media.refresh_from_db(); print(media.friendly_token); print(media.media_type); print(media.get_absolute_url()); print(media.get_absolute_url(api=True)); print(media.original_media_url)"
```

预期：

- `media_type` 输出为 `document`
- 会得到详情页 URL、API URL、原文件下载 URL

### 运行后端检查

```bash
docker compose -f docker-compose-dev.yaml exec -T web python manage.py check
```

### 用 Chromium 做页面级验证

不改项目依赖，直接临时使用 Playwright CLI：

```bash
npx -y playwright@1.60.0 install chromium
```

截图验证示例：

```bash
npx -y -p playwright@1.60.0 playwright screenshot --browser=chromium "http://localhost:8089/search?q=verification" "/tmp/search-page.png"
npx -y -p playwright@1.60.0 playwright screenshot --browser=chromium "http://localhost:8089/view?m=<TOKEN>" "/tmp/document-page.png"
npx -y -p playwright@1.60.0 playwright screenshot --browser=chromium "http://localhost:8089/admin/login/" "/tmp/admin-login.png"
```

### 手工验证重点

1. 搜索页：`/search?q=verification`
   - 展开 `Filters`
   - 确认媒体类型里出现 `Document`

2. 管理页：`/manage_media`（需登录）
   - 确认媒体类型筛选里出现 `Document`

3. 个人页：`/accounts/<username>` 或当前用户媒体页（需登录）
   - 确认媒体类型筛选里出现 `Document`

4. 文档详情页：`/view?m=<TOKEN>`
   - 确认走非视频详情页
   - 确认动作栏仍显示 `DOWNLOAD`
   - 点击后下载原文件

### 本次已验证过的样本

- 示例 token: `ryTmmisl6`
- 详情页: `http://localhost:8089/view?m=ryTmmisl6`
- API: `http://localhost:8089/api/v1/media/ryTmmisl6`

### 注意事项

- 如果本机 Python 环境缺少 Django，优先在 Docker 容器里执行 `manage.py` 命令
- 如果本机前端依赖不完整，不要直接跑本地 `npm run dist`，优先复用 `docker-compose-dev.yaml` 的 `frontend` 服务
- 搜索页未展开 filter 时，不能算验证了 `Document` 筛选项，必须实际展开确认
