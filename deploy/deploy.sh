#!/usr/bin/env bash
# TravelMate 一键部署脚本（Ubuntu / Debian，答辩演示用）
#
# 用法：
#   sudo bash deploy.sh
#   sudo BRANCH=feature/d-agent bash deploy.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://gitee.com/letsgo225/TravelMate.git}"
BRANCH="${BRANCH:-master}"
APP_DIR="${APP_DIR:-/opt/travelmate}"
DATA_DIR="${DATA_DIR:-/var/lib/travelmate}"
SERVICE_NAME="travelmate"
RUN_USER="www-data"

info() { printf "\033[1;32m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[x]\033[0m %s\n" "$*" >&2; exit 1; }

[ "${EUID:-$(id -u)}" -eq 0 ] || die "请用 root 或 sudo 运行"

info "1/8 安装系统依赖"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git nginx sqlite3 curl

info "2/8 获取代码（分支：$BRANCH）"
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" fetch origin
    git -C "$APP_DIR" checkout "$BRANCH"
    git -C "$APP_DIR" pull --ff-only "origin/$BRANCH"
else
    mkdir -p "$APP_DIR"
    git clone -b "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
[ -f "$APP_DIR/app.py" ] || die "代码目录结构异常：$APP_DIR/app.py 不存在"

info "3/8 创建虚拟环境并安装依赖"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

info "4/8 准备数据目录"
mkdir -p "$DATA_DIR"
chown -R "$RUN_USER":"$RUN_USER" "$DATA_DIR"
DB_PATH="$DATA_DIR/travelmate.db"
info "    数据库路径：$DB_PATH"

info "5/8 初始化景点数据（会先清理 core 来源后重建）"
cd "$APP_DIR"
runuser -u "$RUN_USER" -- env TRAVELMATE_DATABASE="$DB_PATH" \
    "$APP_DIR/.venv/bin/python" -m scripts.rebuild_core_attractions
runuser -u "$RUN_USER" -- env TRAVELMATE_DATABASE="$DB_PATH" \
    "$APP_DIR/.venv/bin/python" -m scripts.fill_demo_fields

info "6/8 配置 systemd 服务"
SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")"
sed -e "s#CHANGE_ME_TO_A_RANDOM_STRING#$SECRET_KEY#" \
    -e "s#WorkingDirectory=/opt/travelmate#WorkingDirectory=$APP_DIR#" \
    -e "s#/opt/travelmate/.venv/bin/gunicorn#$APP_DIR/.venv/bin/gunicorn#" \
    -e "s#/var/lib/travelmate/travelmate.db#$DB_PATH#" \
    "$APP_DIR/deploy/travelmate.service" > "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
systemctl restart "$SERVICE_NAME"

info "7/8 配置 Nginx"
sed -e "s#alias /opt/travelmate/static/#alias $APP_DIR/static/#" \
    "$APP_DIR/deploy/nginx.conf" > "/etc/nginx/sites-available/$SERVICE_NAME"
ln -sf "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/$SERVICE_NAME"
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

info "8/8 健康检查"
sleep 3
if curl -fsS -m 10 http://127.0.0.1/api/health >/dev/null; then
    info "服务已就绪"
else
    warn "健康检查失败，请查看日志：journalctl -u $SERVICE_NAME -n 50"
fi

PUBLIC_IP="$(curl -fsS -m 5 https://api.ipify.org 2>/dev/null || hostname -I | awk "{print \$1}")"
cat <<EOF

------------------------------------------------------------
 TravelMate 部署完成

 访问地址   http://$PUBLIC_IP/
 代码目录   $APP_DIR
 数据库     $DB_PATH
 服务管理   systemctl status|restart|stop $SERVICE_NAME
 日志       journalctl -u $SERVICE_NAME -f

 还需要手动做两件事：

 1) 配置 AI 密钥
    mkdir -p $APP_DIR/instance
    写入 $APP_DIR/instance/agent.env 三行：ARK_API_KEY / ARK_MODEL / ARK_BASE_URL
    chown -R $RUN_USER:$RUN_USER $APP_DIR/instance
    systemctl restart $SERVICE_NAME

 2) 创建管理员账号（交互式）
    cd $APP_DIR
    TRAVELMATE_DATABASE=$DB_PATH .venv/bin/python -m scripts.create_admin

 当前为 HTTP 演示模式（Cookie 非 Secure）。
 配好 HTTPS 后请把 systemd 里的 TRAVELMATE_COOKIE_SECURE 改为 1。
------------------------------------------------------------
EOF
