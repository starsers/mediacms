# Google Stitch MCP 完整设置指南

## 前提条件

1. Google Cloud 服务账号密钥 JSON 文件（项目: `clever-overview-497205-h4`）
2. VPN 代理 `http://127.0.0.1:7899`（WSL 不走 Windows VPN，必须显式设代理）
3. Hermes 已安装 `mcp` Python 包（venv 中）

## 安装 mcp 包（Hermes HTTP MCP 依赖）

```bash
# 重建 venv（如果损坏）
uv venv /home/user23/.hermes/venv --python 3.11

# 走 VPN 安装 mcp 包
HTTPS_PROXY=http://127.0.0.1:7899 HTTP_PROXY=http://127.0.0.1:7899 \
  uv pip install --python /home/user23/.hermes/venv/bin/python mcp
```

## 配置代理

在 `~/.hermes/.env` 中加（Hermes 进程需要代理访问 stitch.googleapis.com）：

```
HTTPS_PROXY=http://127.0.0.1:7899
HTTP_PROXY=http://127.0.0.1:7899
```

改完后 `/reload` 加载环境变量。

## 生成 Access Token（1小时有效，过期需重生成）

```bash
# 1. 签 JWT
python3 /tmp/gen_jwt.py "/mnt/c/Users/123/Downloads/clever-overview-497205-h4-ffc2365bdbbb.json" > /tmp/jwt.txt

# 2. 走 VPN 换 token
JWT=$(cat /tmp/jwt.txt)
curl -s -x http://127.0.0.1:7899 -X POST https://oauth2.googleapis.com/token \
  -d "grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer" \
  -d "assertion=$JWT" -o /tmp/token.json

# 3. 提取 access_token
python3 -c "import json; d=json.load(open('/tmp/token.json')); print(d['access_token'])"
```

## 配置 Stitch MCP 到 Hermes

`~/.hermes/config.yaml` → `mcp_servers`:

```yaml
  stitch:
    url: https://stitch.googleapis.com/mcp
    timeout: 60
    headers:
      Authorization: Bearer <access_token>
      X-Goog-User-Project: clever-overview-497205-h4
```

⚠️ **Token 1小时后过期**，需要重新生成并更新 config.yaml。更新后用 `/reload-mcp` 重连。

## 可用模型（modelId）

| modelId | 说明 |
|---------|------|
| `GEMINI_3_1_PRO` | 最新，最强大 ⭐ |
| `GEMINI_3_FLASH` | 快速版本 |
| `GEMINI_3_PRO` | 已废弃 |
| 默认（不指定） | 自动选择 |

## 踩坑记录

- **`mcp` 包未装**: URL-based MCP 服务器需要 `mcp` Python 包。`hermes mcp test` 会超时但无明确错误。
- **Token 被安全扫描截断**: 不要用 heredoc/echo 把 token 写到 config.yaml。用脚本从文件读取再 `str.replace()`。
- **WSL 不走 VPN**: 所有 Google API 调用必须显式走代理 `-x http://127.0.0.1:7899`。
- **projectId 格式**: 纯数字字符串（如 `17239077371614721644`），不含 `projects/` 前缀。
- **modelId 用枚举值**: `GEMINI_3_1_PRO`（不是 `gemini-3.1-pro` 或 `nano-banana-pro`）。
