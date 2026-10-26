#!/usr/bin/env bash
set -euo pipefail
cd /opt/afvc
docker compose ps
ss -lntp | grep 55433 || true
if [[ ! -f .env ]]; then
  cp deploy/env.demo.example .env
fi
chmod 600 .env
chown afvc:afvc .env
grep -E '^(AFVC_DATA_PROFILE|DATABASE_URL|AFVC_USE_LLM|OPENAI_MODEL)=' .env || true

cp deploy/afvc.service /etc/systemd/system/afvc.service
systemctl daemon-reload
systemctl enable --now afvc
sleep 5
systemctl is-active afvc
curl -fsS http://127.0.0.1:8000/health
echo

PASS="$(openssl rand -base64 18 | tr -d '/+=' | head -c 16)"
printf '%s' "$PASS" > /root/afvc-admin.pass
chmod 600 /root/afvc-admin.pass
printf '%s' "$PASS" | /opt/afvc/.venv/bin/python -m backend.scripts.manage_user create afvcadmin --password-stdin

curl -fsS -c /tmp/afvc.cj -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"afvcadmin\",\"password\":\"${PASS}\"}"
echo
curl -fsS -b /tmp/afvc.cj http://127.0.0.1:8000/usecases/devices | head -c 240
echo
curl -s -o /dev/null -w 'local_http=%{http_code}\n' http://127.0.0.1/
echo 'ADMIN_USER=afvcadmin'
echo 'PASSWORD_FILE=/root/afvc-admin.pass'
echo 'DONE'
