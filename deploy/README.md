# AFVC ECS Demo 部署

目标：公网 **80**（有域名后再开 **443**）提供站点；**8000 / 55433 仅本机**；`AFVC_DATA_PROFILE=demo`；DeepSeek `deepseek-flash`；固定账号门禁。

## 1. 服务器准备（勿替换系统 Python 3.6）

以 `/opt/afvc` 为例。需要：Docker + Compose、Nginx、独立 **Python 3.12**。

### 独立 Python 3.12（示例：官方源码 / 预编译）

任选其一，只要 `python3.12 -m venv` 可用即可：

```bash
# 示例 A：miniconda（不改动 /usr/bin/python）
# 按官方安装脚本装到 $HOME/miniconda3 后：
conda create -y -n afvc python=3.12
# 或示例 B：从 python.org 安装到 /usr/local（确保不覆盖系统 3.6）
```

创建运行用户与目录：

```bash
sudo useradd -r -m -d /opt/afvc -s /bin/bash afvc || true
sudo mkdir -p /opt/afvc
sudo chown -R afvc:afvc /opt/afvc
```

安全组 / 防火墙：放行 **80**（及日后 **443**）；**不要**对公网放行 8000、55433。

## 2. 本机打包同步

```powershell
cd frontend
npm ci
npm run build
cd ..
.\deploy\sync-to-server.ps1 -Remote "USER@ECS_PUBLIC_IP" -RemotePath "/opt/afvc"
```

排除项见 [rsync-exclude.txt](./rsync-exclude.txt)：`.env`、密钥、`backend/data/raw` 真实工单、venv、缓存等。**不要**把本机 `.env` 或 DeepSeek Key 传上服务器。

## 3. 服务器现场配置

```bash
cd /opt/afvc
cp deploy/env.demo.example .env
# 编辑 .env：填入 OPENAI_API_KEY；确认 DATABASE_URL=...127.0.0.1:55433/afvc_demo

docker compose up -d
# 等待 postgres healthy

# 用独立 3.12 建 venv（路径按你的安装调整）
/path/to/python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

sudo cp deploy/afvc.service /etc/systemd/system/afvc.service
sudo systemctl daemon-reload
sudo systemctl enable --now afvc

sudo cp deploy/nginx-afvc.conf /etc/nginx/conf.d/afvc.conf
sudo nginx -t && sudo systemctl reload nginx

# 创建首个账号（交互输入密码，勿写进聊天/仓库）
python -m backend.scripts.manage_user create YOUR_USERNAME
```

验收：`curl -s http://127.0.0.1:8000/health`；浏览器打开 `http://ECS_PUBLIC_IP/` → 登录 → 业务页；对话路径需 `AFVC_USE_LLM=true` 与有效 Key。

## 4. 账号运维

```bash
python -m backend.scripts.manage_user create alice
python -m backend.scripts.manage_user disable alice
python -m backend.scripts.manage_user enable alice
python -m backend.scripts.manage_user reset-password alice
```

无自助注册。停用后既有会话立即失效。

## 5. Demo 库重置

先停 `afvc` 服务，再：

```bash
docker compose down --volumes
docker compose up -d
sudo systemctl start afvc
```

仅清空当前 `afvc-demo` Compose 卷；账号表一并清空，需重新 `manage_user create`。
