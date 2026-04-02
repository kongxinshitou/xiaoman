#!/bin/bash
set -e

SECRETS_FILE="/secrets/app.env"

if [ ! -f "$SECRETS_FILE" ]; then
    echo "[xiaoman] First run: generating application secrets..."
    mkdir -p /secrets
    python3 -c "
import secrets
from cryptography.fernet import Fernet
print('SECRET_KEY=' + secrets.token_urlsafe(32))
print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())
" > "$SECRETS_FILE"
    echo "[xiaoman] Secrets saved."
fi

set -a
source "$SECRETS_FILE"
set +a

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
