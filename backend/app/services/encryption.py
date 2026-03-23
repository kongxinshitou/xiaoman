import os
import base64
from cryptography.fernet import Fernet
from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        # Generate a new key and persist it to .env
        new_key = Fernet.generate_key().decode()
        settings.encryption_key = new_key
        env_path = ".env"
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                content = f.read()
            if "ENCRYPTION_KEY=" in content:
                lines = content.splitlines()
                new_lines = []
                for line in lines:
                    if line.startswith("ENCRYPTION_KEY="):
                        new_lines.append(f"ENCRYPTION_KEY={new_key}")
                    else:
                        new_lines.append(line)
                with open(env_path, "w") as f:
                    f.write("\n".join(new_lines))
            else:
                with open(env_path, "a") as f:
                    f.write(f"\nENCRYPTION_KEY={new_key}\n")
        key = new_key
    # Ensure key is valid Fernet key (32 url-safe base64 bytes)
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        new_key = Fernet.generate_key().decode()
        settings.encryption_key = new_key
        return Fernet(new_key.encode())


def encrypt(text: str) -> str:
    f = _get_fernet()
    return f.encrypt(text.encode()).decode()


def decrypt(text: str) -> str:
    try:
        f = _get_fernet()
        return f.decrypt(text.encode()).decode()
    except Exception:
        # Return as-is if decryption fails (e.g., plaintext stored)
        return text
