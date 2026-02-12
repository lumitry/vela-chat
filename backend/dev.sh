PORT="${PORT:-8080}"
# Enable connection pooling for remote databases (defaults to 0 which uses NullPool - very slow!)
export DATABASE_POOL_SIZE="${DATABASE_POOL_SIZE:-10}"
export DATABASE_POOL_MAX_OVERFLOW="${DATABASE_POOL_MAX_OVERFLOW:-5}"
uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --forwarded-allow-ips '*' --reload