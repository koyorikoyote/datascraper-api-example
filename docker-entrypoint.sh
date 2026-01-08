#!/usr/bin/env bash
set -e

TARGET=/app/alembic/versions        # directory Alembic writes into
APP_USER=seluser                    # runtime UID created by Selenium image

# ── 0) If we’re running as root, fix permissions on bind-mounted folder ──────
if [ "$(id -u)" = "0" ]; then
  if [ "$(stat -c '%U' "$TARGET" 2>/dev/null || echo root)" != "$APP_USER" ]; then
    echo "🛠  Adjusting ownership of $TARGET → $APP_USER"
    chown -R "$APP_USER":"$APP_USER" "$TARGET" || true
  fi
fi

# ── 1) Launch Selenium Grid in background with increased session timeout ────
# Create a custom Selenium Grid config file with 2-hour timeout
mkdir -p /opt/selenium/config
cat > /opt/selenium/config/config.toml << EOF
[network]
relax-checks = true

[node]
session-timeout = 7200
override-max-sessions = false
detect-drivers = false
drain-after-session-count = 0
EOF

# Set environment variables for extra safety
export SE_NODE_SESSION_TIMEOUT=7200
export SE_SESSION_REQUEST_TIMEOUT=7200

# Launch Selenium Grid with the custom config
/opt/bin/entry_point.sh -nodeConfig /opt/selenium/config/config.toml &
SEL_PID=$!

echo "Waiting for Selenium Grid to be ready …"
until curl -s http://localhost:4444/status | grep -q '"ready":[[:space:]]*true'; do
  sleep 1
done
echo "✅  Selenium Grid is up!"

# ── 2) Drop privileges & start FastAPI in foreground ────────────────────────
exec gosu "$APP_USER" uvicorn src.main:app \
        --host 0.0.0.0 --port 8000 \
        --reload --reload-dir /app/src
