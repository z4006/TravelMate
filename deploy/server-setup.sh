#!/usr/bin/env bash
# 服务器初始化（无需 Git）：假设代码已同步到 $APP_DIR
#
# 用法（在服务器上，root 执行）：
#   bash /opt/travelmate/deploy/server-setup.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/travelmate}"
DATA_DIR="${DATA_DIR:-/var/lib/travelmate}"
RUN_USER="www-data"

info() { printf "\n\033[1;32m==>\033[0m %s\n" "$*"; }

[ "${EUID:-$(id -u)}" -eq 0 ] || { echo "请用 root 运行"; exit 1; }
[ -f "$APP_DIR/app.py" ] || { echo "找不到 $APP_DIR/app.py，请先同步代码"; exit 1; }

info "1/6 安装系统依赖"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv nginx sqlite3 curl

info "2/6 创建虚拟环境并安装依赖"
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

info "3/6 准备数据目录"
mkdir -p "$DATA_DIR"
chown -R "$RUN_USER":"$RUN_USER" "$DATA_DIR"
DB="$DATA_DIR/travelmate.db"

info "4/6 初始化景点数据"
runuser -u "$RUN_USER" -- env TRAVELMATE_DATABASE="$DB" \
    "$APP_DIR/.venv/bin/python" -m scripts.rebuild_core_attractions
runuser -u "$RUN_USER" -- env TRAVELMATE_DATABASE="$DB" \
    "$APP_DIR/.venv/bin/python" -m scripts.fill_demo_fields

info "5/6 配置 systemd"
SECRET="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")"
sed -e "s#CHANGE_ME_TO_A_RANDOM_STRING#$SECRET#" \
    "$APP_DIR/deploy/travelmate.service" > /etc/systemd/system/travelmate.service
systemctl daemon-reload
systemctl enable travelmate >/dev/null 2>&1 || true
systemctl restart travelmate

info "6/6 配置 Nginx"
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/travelmate
ln -sf /etc/nginx/sites-available/travelmate /etc/nginx/sites-enabled/travelmate
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

sleep 3
info "健康检查"
echo -n "  应用直连: "; curl -fsS -m 10 http://127.0.0.1:8000/api/health || echo "失败"
echo
echo -n "  Nginx:    "; curl -fsS -m 10 http://127.0.0.1/api/health || echo "失败"
echo
echo
echo "完成。服务状态："
systemctl is-active travelmate nginx || true
