# 部署指南（答辩演示用）

适用于：一台云服务器、直接通过公网 IP 访问、暂不配置域名和证书。

## 快速方式：一键脚本

新服务器上执行：

```bash
git clone https://gitee.com/letsgo225/TravelMate.git /tmp/tm
sudo bash /tmp/tm/deploy/deploy.sh
```

指定分支：

```bash
sudo BRANCH=feature/d-agent bash /tmp/tm/deploy/deploy.sh
```

脚本会自动完成：装依赖、拉代码、建虚拟环境、初始化数据、配置 systemd 与 Nginx、
健康检查，最后打印访问地址和待办事项。

脚本跑完后仍**需要手动**做两件事：配置 AI 密钥（`instance/agent.env`）和
创建管理员账号（`scripts.create_admin`，交互式）。

下面是手动模式的分步说明，遇到问题时可对照排查。

## 0. 前置条件

- 服务器：1 核 2G 起，Ubuntu 22.04 / Debian 12
- 安全组放行：22（SSH）、80（HTTP）
- 服务器能访问 `ark.cn-beijing.volces.com`（AI 助手需要）
- 本地代码已推送到 Gitee

## 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx sqlite3
```

## 2. 拉取代码

```bash
sudo mkdir -p /opt/travelmate
sudo chown "$USER":"$USER" /opt/travelmate

git clone https://gitee.com/letsgo225/TravelMate.git /opt/travelmate
cd /opt/travelmate
# 如果开发分支还没合并进 master：
# git checkout feature/d-agent
```

## 3. 创建虚拟环境并安装依赖

```bash
cd /opt/travelmate
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

## 4. 准备数据目录

```bash
sudo mkdir -p /var/lib/travelmate
sudo chown www-data:www-data /var/lib/travelmate
```

## 5. 配置密钥

```bash
cd /opt/travelmate
mkdir -p instance
cat > instance/agent.env <<'EOF'
ARK_API_KEY=你的密钥
ARK_MODEL=DeepSeek-V4.1-Flash-Economy
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/plan/v1
EOF
chmod 600 instance/agent.env
```

`instance/` 已被 `.gitignore` 忽略，不会进仓库。

## 6. 初始化数据库

```bash
cd /opt/travelmate
export TRAVELMATE_DATABASE=/var/lib/travelmate/travelmate.db

.venv/bin/python -m scripts.rebuild_core_attractions
.venv/bin/python -m scripts.fill_demo_fields
.venv/bin/python -m scripts.create_admin
```

注意：`TRAVELMATE_DATABASE` 必须与 systemd 服务里配置的一致，否则会写到两个不同的库。

## 7. 配置 systemd

```bash
sudo cp deploy/travelmate.service /etc/systemd/system/travelmate.service
sudo nano /etc/systemd/system/travelmate.service   # 修改 SECRET_KEY
sudo systemctl daemon-reload
sudo systemctl enable --now travelmate
sudo systemctl status travelmate
```

`TRAVELMATE_SECRET_KEY` 生成方式：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 8. 配置 Nginx

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/travelmate
sudo ln -sf /etc/nginx/sites-available/travelmate /etc/nginx/sites-enabled/travelmate
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

## 9. 验证

```bash
curl -s http://127.0.0.1:8000/api/health        # 直接访问 gunicorn
curl -s http://127.0.0.1/api/health             # 经过 Nginx
```

浏览器打开 `http://服务器公网IP/`。

## 10. 常见问题

### 登录成功但仍是未登录状态

原因：`SESSION_COOKIE_SECURE=True`，浏览器拒绝在 HTTP 下保存 Cookie。

处理：没有 HTTPS 时，在 systemd 里设置 `TRAVELMATE_COOKIE_SECURE=0`，然后
`sudo systemctl restart travelmate`。配好证书后改回 `1`。

### 502 Bad Gateway

gunicorn 没起来：

```bash
sudo systemctl status travelmate
sudo journalctl -u travelmate -n 50
```

### AI 助手一直转圈或报超时

- 检查服务器能否访问方舟接口：`curl -m 10 https://ark.cn-beijing.volces.com`
- 检查 `/opt/travelmate/instance/agent.env` 是否配置正确
- Nginx 的 `proxy_read_timeout` 已设为 60s

### 数据是空的

数据库文件不在 Git 里，必须跑第 6 步的初始化脚本。

## 11. 更新代码

```bash
cd /opt/travelmate
sudo systemctl stop travelmate
git pull
.venv/bin/pip install -r requirements.txt
export TRAVELMATE_DATABASE=/var/lib/travelmate/travelmate.db
.venv/bin/python -m scripts.rebuild_core_attractions
.venv/bin/python -m scripts.fill_demo_fields
sudo systemctl start travelmate
```

## 12. 备份

```bash
# 手动备份
sqlite3 /var/lib/travelmate/travelmate.db \
    ".backup /var/lib/travelmate/backup-$(date +%F).db"

# 每天凌晨 3 点自动备份
echo '0 3 * * * sqlite3 /var/lib/travelmate/travelmate.db ".backup /var/lib/travelmate/backup-$(date +\%F).db"' \
    | sudo crontab -
```

## 13. 演示前的检查清单

- [ ] `systemctl status travelmate` 是 active
- [ ] `curl http://127.0.0.1/api/health` 返回 `{"success": true}`
- [ ] 浏览器能打开首页，景点列表有数据
- [ ] 能注册 / 登录，刷新后仍保持登录
- [ ] 收藏、行程可用
- [ ] `/agent` 能生成行程（首次请求较慢属正常）
- [ ] 服务器时间正确：`date`
