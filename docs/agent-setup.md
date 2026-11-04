# AI 助手接入说明（成员 D）

TravelMate 的 AI 助手基于火山引擎方舟（Ark）的 OpenAI 兼容接口，默认调用
DeepSeek 系列模型。代码只依赖 Python 标准库，不需要安装额外 SDK。

## 1. 配置密钥

在项目根目录创建 `instance/agent.env`：

```bash
mkdir -p instance
cat > instance/agent.env <<'EOF'
ARK_API_KEY=你的密钥
ARK_MODEL=你的模型ID
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/plan/v1
EOF
chmod 600 instance/agent.env
```

说明：

- `instance/` 已被 `.gitignore` 忽略，**密钥不会进仓库**，每个人本地各自配置；
- `ARK_MODEL` 填控制台里的模型标识，不同账号的可用模型可能不同；
- `ARK_BASE_URL` 按所用产品线填写：标准方舟为 `https://ark.cn-beijing.volces.com/api/v3`，
  「Agent Plan」企业版为 `https://ark.cn-beijing.volces.com/api/plan/v1`；
- 也可以用环境变量覆盖同名配置。

未配置密钥时，接口会自动降级为规则版行程，页面仍可正常演示。

## 2. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/agent/status` | 查询模型是否已配置 |
| POST | `/api/agent/chat` | 旅行问答，支持回传多轮历史 |
| POST | `/api/agent/plan` | 按自然语言需求生成行程，可一键保存 |

写操作需要登录并携带 `X-CSRF-Token`。

### `POST /api/agent/chat`

```json
{
  "message": "西安城墙门票多少？",
  "history": [
    {"role": "user", "content": "上一轮问题"},
    {"role": "assistant", "content": "上一轮回答"}
  ]
}
```

返回：

```json
{
  "success": true,
  "message": "操作成功",
  "data": {"reply": "...", "source": "model", "model_configured": true}
}
```

### `POST /api/agent/plan`

```json
{
  "message": "想去西安玩两天，喜欢历史古迹",
  "days": 2,
  "city": "西安市",
  "start_date": "2026-11-10",
  "save": false
}
```

返回 `data` 包含：

- `source`：`model` 或 `rule`（是否使用了真实模型）；
- `plan`：按天组织的行程，每个景点带 `attraction_id`、`name`、`city`、`note`；
- `itinerary_payload`：可直接提交给 `POST /api/itineraries` 的结构；
- `saved`：当 `save=true` 时返回已保存的行程。

## 3. 安全约束

1. 模型返回的 `attraction_id` 会在服务端二次校验，不存在于景点库的直接剔除，防止编造；
2. 密钥只从配置文件或环境变量读取，不写日志、不进仓库；
3. 提示词要求模型只能依据景点库回答，信息不足时明确说明，不允许编造门票和开放时间。

## 4. 运行测试

```bash
.venv/bin/python -m pytest -q
```

`tests/test_agent.py` 使用假响应，不会真实消耗 token。
