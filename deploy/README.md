# 部署文件说明

| 文件 | 用途 |
| --- | --- |
| `deploy.sh` | **一键部署脚本**，自动完成下面全部步骤 |
| `travelmate.service` | systemd 服务，守护 gunicorn 并开机自启 |
| `nginx.conf` | Nginx 站点配置，反代到 127.0.0.1:8000 |

完整步骤见 `docs/deployment.md`。
