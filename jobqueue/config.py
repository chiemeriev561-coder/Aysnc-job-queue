import os
from pathlib import Path

# Automatically find and load .env file if it exists
ENV_PATH = Path(__file__).resolve().parent / ".env"

def _load_env():
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = val

_load_env()

# Standard database connection string from environment or .env
DB_DSN = os.getenv("DB_DSN") or os.getenv("DATABASE_URL") or "postgresql://user:password@localhost:5432/yourdb"
