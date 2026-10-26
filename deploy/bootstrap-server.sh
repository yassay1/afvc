#!/usr/bin/env bash
# Run on the ECS host as root after code is synced to /opt/afvc.
# Does NOT write OPENAI_API_KEY; edit /opt/afvc/.env yourself.
set -euo pipefail

AFVC_ROOT="${AFVC_ROOT:-/opt/afvc}"
cd "$AFVC_ROOT"

echo "==> Ensure afvc user and ownership"
id afvc >/dev/null 2>&1 || useradd -r -m -d "$AFVC_ROOT" -s /bin/bash afvc
chown -R afvc:afvc "$AFVC_ROOT"

echo "==> Install Docker CE (do not use podman-docker)"
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  dnf -y remove podman-docker podman 2>/dev/null || true
  dnf -y install dnf-plugins-core || true
  dnf config-manager --add-repo=https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo || true
  dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin --allowerasing
  systemctl enable --now docker
fi
docker --version
docker compose version

echo "==> Install Nginx if missing"
if ! command -v nginx >/dev/null 2>&1; then
  dnf -y install nginx || yum -y install nginx
fi
systemctl enable --now nginx

echo "==> Independent Python 3.12 via Miniconda (leave system python alone)"
CONDA_ROOT="${CONDA_ROOT:-/opt/miniconda3}"
if [[ ! -x "$CONDA_ROOT/bin/conda" ]]; then
  curl -fL --retry 3 -o /tmp/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  bash /tmp/miniconda.sh -b -p "$CONDA_ROOT"
  rm -f /tmp/miniconda.sh
fi
"$CONDA_ROOT/bin/conda" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true
"$CONDA_ROOT/bin/conda" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true
"$CONDA_ROOT/bin/conda" create -y -p /opt/afvc-py312 python=3.12
PY312=/opt/afvc-py312/bin/python
usermod -aG docker afvc || true

echo "==> Demo Postgres (pull via mirror if Docker Hub is slow)"
if ! docker image inspect postgres:16-alpine >/dev/null 2>&1; then
  docker pull docker.m.daocloud.io/library/postgres:16-alpine
  docker tag docker.m.daocloud.io/library/postgres:16-alpine postgres:16-alpine
fi
cd "$AFVC_ROOT"
docker compose up --detach

echo "==> App venv + deps"
if [[ ! -x "$AFVC_ROOT/.venv/bin/python" ]]; then
  sudo -u afvc "$PY312" -m venv "$AFVC_ROOT/.venv"
fi
sudo -u afvc "$AFVC_ROOT/.venv/bin/pip" install -U pip
sudo -u afvc "$AFVC_ROOT/.venv/bin/pip" install -r "$AFVC_ROOT/requirements.txt"

if [[ ! -f "$AFVC_ROOT/.env" ]]; then
  sudo -u afvc cp "$AFVC_ROOT/deploy/env.demo.example" "$AFVC_ROOT/.env"
  chmod 600 "$AFVC_ROOT/.env"
  echo "Wrote $AFVC_ROOT/.env — fill OPENAI_API_KEY before enabling LLM."
fi

echo "==> systemd + nginx"
cp "$AFVC_ROOT/deploy/afvc.service" /etc/systemd/system/afvc.service
# Point ExecStart python stays at /opt/afvc/.venv
systemctl daemon-reload
systemctl enable --now afvc

cp "$AFVC_ROOT/deploy/nginx-afvc.conf" /etc/nginx/conf.d/afvc.conf
# Drop default conflicting server if present
rm -f /etc/nginx/conf.d/default.conf || true
nginx -t
systemctl reload nginx

echo "==> Local health"
curl -fsS http://127.0.0.1:8000/health || true
echo
echo "Next: edit .env OPENAI_API_KEY; systemctl restart afvc;"
echo "      sudo -u afvc $AFVC_ROOT/.venv/bin/python -m backend.scripts.manage_user create <user>"
