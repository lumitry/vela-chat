#!/bin/bash
# Complete test run script: stops app, clears DB, starts app, runs tests
#
# This script performs destructive database operations. It requires ALLOW_DB_CLEAR=true to be set as a safety measure.
#
# Environment variables:
#   ALLOW_DB_CLEAR - Must be set to "true" to allow database clearing (required)
#   DATABASE_URL - PostgreSQL connection string (defaults to test DB)
#   CONDA_ENV - Conda environment name for backend (defaults to "velachat")
#   PORT - Backend server port (defaults to 8080)
#   MINI_MEDIATOR_IP - mini-mediator host (defaults to "localhost", can be overridden in tests/mocks/mini-mediator/.env)
#   MINI_MEDIATOR_PORT - mini-mediator port (defaults to 11998, can be overridden in tests/mocks/mini-mediator/.env)
#
# Usage:
#   ALLOW_DB_CLEAR=true npm run test:e2e:complete
#   or
#   ALLOW_DB_CLEAR=true ./scripts/complete_test_run.sh

set -e

# Source .env file if it exists (loads DATABASE_URL, CONDA_ENV, etc.)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ -f "$PROJECT_ROOT/.env" ]; then
	set -a  # automatically export all variables
	source "$PROJECT_ROOT/.env"
	set +a
fi

# Safety check
if [ "${ALLOW_DB_CLEAR}" != "true" ]; then
	echo "❌ ERROR: This script performs destructive database operations."
	echo "   Set ALLOW_DB_CLEAR=true to proceed."
	echo ""
	echo "   Example: ALLOW_DB_CLEAR=true npm run test:e2e:complete"
	exit 1
fi

# Configuration
CONDA_ENV="${CONDA_ENV:-velachat}"
export PORT="${PORT:-8080}"  # Export so backend dev.sh can use it
DB_URL="${DATABASE_URL:-postgresql://testuser:testpass@localhost:5432/velachat_test}"
BACKEND_DIR="$PROJECT_ROOT/backend"
APP_PID_FILE="/tmp/velachat-test-app.pid"
MINI_MEDIATOR_DIR="$PROJECT_ROOT/tests/mocks/mini-mediator"
MINI_MEDIATOR_PID_FILE="/tmp/velachat-mini-mediator.pid"

# Load mini-mediator config from .env if it exists
MINI_MEDIATOR_IP="${MINI_MEDIATOR_IP:-localhost}"
MINI_MEDIATOR_PORT="${MINI_MEDIATOR_PORT:-11998}"
if [ -f "$MINI_MEDIATOR_DIR/.env" ]; then
	set -a
	source "$MINI_MEDIATOR_DIR/.env"
	set +a
	# Re-read after sourcing .env in case it was set there
	MINI_MEDIATOR_IP="${MINI_MEDIATOR_IP:-localhost}"
	MINI_MEDIATOR_PORT="${MINI_MEDIATOR_PORT:-11998}"
fi

# Helper function to sanitize database URL for display (masks password)
sanitize_db_url() {
	local url="$1"
	# Replace password with *** in connection string
	echo "$url" | sed -E 's|://([^:]+):([^@]+)@|://\1:***@|'
}

# Helper function to kill processes by port (more robust than pkill)
kill_by_port() {
	local port="$1"
	local pids=$(lsof -ti:"$port" 2>/dev/null || true)
	if [ -n "$pids" ]; then
		# Try graceful kill first
		echo "$pids" | xargs kill -TERM 2>/dev/null || true
		sleep 0.5
		# Force kill if still running
		local remaining=$(lsof -ti:"$port" 2>/dev/null || true)
		if [ -n "$remaining" ]; then
			echo "$remaining" | xargs kill -9 2>/dev/null || true
		fi
	fi
}

# Helper function to check if mini-mediator is already running
is_mini_mediator_running() {
	# Check if port is in use
	local port_in_use=$(lsof -ti:"${MINI_MEDIATOR_PORT}" 2>/dev/null || true)
	if [ -n "$port_in_use" ]; then
		# Also check if it responds to health check
		if curl -s "http://${MINI_MEDIATOR_IP}:${MINI_MEDIATOR_PORT}/healthz" > /dev/null 2>&1; then
			return 0  # Running and healthy
		fi
		# Port is in use but health check failed - might be something else using the port
		# Return 1 so we try to start (will fail with clear error if port conflict)
		return 1
	fi
	return 1  # Not running
}

# Helper function to kill all app processes (comprehensive)
kill_app_processes() {
	echo "   Killing processes by pattern..."
	# Kill by process name patterns (multiple patterns to catch different invocations)
	pkill -f "uvicorn.*open_webui" 2>/dev/null || true
	pkill -f "uvicorn.*main:app" 2>/dev/null || true
	pkill -f "python.*uvicorn" 2>/dev/null || true
	pkill -f "vite dev" 2>/dev/null || true
	pkill -f "vite.*5173" 2>/dev/null || true
	pkill -f "node.*vite" 2>/dev/null || true
	
	echo "   Killing processes by port..."
	# Kill by port (most reliable method)
	# Use $PORT variable (defaults to 8080) to match what the backend actually uses
	kill_by_port "${PORT}"  # Backend port
	kill_by_port 5173  # Frontend port (vite default)
	
	# Give processes time to die
	sleep 1
	
	# Verify ports are free
	local backend_port=$(lsof -ti:"${PORT}" 2>/dev/null || true)
	local frontend_port=$(lsof -ti:5173 2>/dev/null || true)
	
	if [ -n "$backend_port" ] || [ -n "$frontend_port" ]; then
		echo "   ⚠️  Some processes still holding ports, force killing..."
		[ -n "$backend_port" ] && echo "$backend_port" | xargs kill -9 2>/dev/null || true
		[ -n "$frontend_port" ] && echo "$frontend_port" | xargs kill -9 2>/dev/null || true
		sleep 0.5
	fi
}

# Cleanup function
cleanup() {
	echo ""
	echo "🧹 Cleaning up..."
	
	# Stop mini-mediator by PID if we started it (only if we tracked it)
	if [ -f "$MINI_MEDIATOR_PID_FILE" ]; then
		MINI_MEDIATOR_PID=$(cat "$MINI_MEDIATOR_PID_FILE" 2>/dev/null || true)
		if [ -n "$MINI_MEDIATOR_PID" ] && ps -p "$MINI_MEDIATOR_PID" > /dev/null 2>&1; then
			echo "   Stopping mini-mediator (PID: $MINI_MEDIATOR_PID)..."
			kill -TERM "$MINI_MEDIATOR_PID" 2>/dev/null || true
			sleep 0.5
			# Force kill if still running
			if ps -p "$MINI_MEDIATOR_PID" > /dev/null 2>&1; then
				kill -9 "$MINI_MEDIATOR_PID" 2>/dev/null || true
			fi
		fi
		rm -f "$MINI_MEDIATOR_PID_FILE"
	fi
	
	# Stop backend by PID if we tracked it
	if [ -f "$APP_PID_FILE" ]; then
		BACKEND_PID=$(head -n 1 "$APP_PID_FILE" 2>/dev/null || true)
		if [ -n "$BACKEND_PID" ] && ps -p "$BACKEND_PID" > /dev/null 2>&1; then
			kill -TERM "$BACKEND_PID" 2>/dev/null || true
			sleep 0.5
			# Force kill if still running
			if ps -p "$BACKEND_PID" > /dev/null 2>&1; then
				kill -9 "$BACKEND_PID" 2>/dev/null || true
			fi
		fi
		FRONTEND_PID=$(tail -n 1 "$APP_PID_FILE" 2>/dev/null || true)
		if [ -n "$FRONTEND_PID" ] && [ "$FRONTEND_PID" != "$BACKEND_PID" ] && ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
			kill -TERM "$FRONTEND_PID" 2>/dev/null || true
			sleep 0.5
			# Force kill if still running
			if ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
				kill -9 "$FRONTEND_PID" 2>/dev/null || true
			fi
		fi
		rm -f "$APP_PID_FILE"
	fi
	
	# Kill any remaining processes (comprehensive cleanup)
	kill_app_processes
}
trap cleanup EXIT

echo "🧪 Complete Test Run"
echo ""

# Step 1: Stop app if running
echo "🛑 Stopping app (if running)..."
kill_app_processes
echo "✅ App stopped"

# Step 2: Clear database
echo ""
echo "🗑️  Clearing database..."
echo "   Database: $(sanitize_db_url "$DB_URL")"

# Disconnect all active sessions
# (these should have already been disconnected by the app stopping, but just in case...)
psql "$DB_URL" -c "
	SELECT pg_terminate_backend(pg_stat_activity.pid)
	FROM pg_stat_activity
	WHERE pg_stat_activity.datname = current_database()
		AND pid <> pg_backend_pid();
" > /dev/null 2>&1 || true

sleep 0.5

# Truncate all tables EXCEPT migration tracking tables
# We need to preserve alembic_version and migratehistory so the app knows migrations have run
psql "$DB_URL" -c "
	DO \$\$ 
	DECLARE 
		r RECORD;
	BEGIN
		FOR r IN (
			SELECT tablename 
			FROM pg_tables 
			WHERE schemaname = 'public' 
				AND tablename NOT IN ('alembic_version', 'migratehistory')
		) 
		LOOP
			EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' RESTART IDENTITY CASCADE';
		END LOOP;
	END \$\$;
" > /dev/null

echo "✅ Database cleared"

# Step 3: Start mini-mediator (if not already running)
echo ""
echo "🤖 Starting mini-mediator..."
if is_mini_mediator_running; then
	echo "   ✅ mini-mediator is already running on ${MINI_MEDIATOR_IP}:${MINI_MEDIATOR_PORT}"
	echo "   ℹ️  Skipping startup (using existing instance)"
else
	echo "   Starting new instance on ${MINI_MEDIATOR_IP}:${MINI_MEDIATOR_PORT}..."
	cd "$MINI_MEDIATOR_DIR"
	source "$(conda info --base)/etc/profile.d/conda.sh"
	conda activate "$CONDA_ENV"
	python mini_mediator.py > /tmp/velachat-mini-mediator.log 2>&1 &
	MINI_MEDIATOR_PID=$!
	echo "$MINI_MEDIATOR_PID" > "$MINI_MEDIATOR_PID_FILE"
	cd - > /dev/null
	echo "   ✅ mini-mediator started (PID: $MINI_MEDIATOR_PID)"
	
	# Wait for mini-mediator to be ready
	echo "   ⏳ Waiting for mini-mediator to be ready..."
	for i in {1..30}; do
		if curl -s "http://${MINI_MEDIATOR_IP}:${MINI_MEDIATOR_PORT}/healthz" > /dev/null 2>&1; then
			echo "   ✅ mini-mediator is ready!"
			break
		fi
		if [ $i -eq 30 ]; then
			echo "   ❌ mini-mediator failed to start after 30 seconds"
			echo "      Log: tail -f /tmp/velachat-mini-mediator.log"
			exit 1
		fi
		sleep 1
	done
fi

# Step 4: Start backend
echo ""
echo "🚀 Starting backend..."
cd "$BACKEND_DIR"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"
./dev.sh > /tmp/velachat-backend.log 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$APP_PID_FILE"
cd - > /dev/null
echo "✅ Backend started (PID: $BACKEND_PID)"

# Step 5: Start frontend
echo ""
echo "🚀 Starting frontend..."
npm run dev > /tmp/velachat-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" >> "$APP_PID_FILE"
echo "✅ Frontend started (PID: $FRONTEND_PID)"

# Step 6: Wait for app to be ready
echo ""
echo "⏳ Waiting for app to be ready..."
for i in {1..60}; do
	if curl -s http://localhost:5173 > /dev/null 2>&1; then
		echo "✅ App is ready!"
		break
	fi
	if [ $i -eq 60 ]; then
		echo "❌ App failed to start after 60 seconds"
		echo "   Backend log: tail -f /tmp/velachat-backend.log"
		echo "   Frontend log: tail -f /tmp/velachat-frontend.log"
		exit 1
	fi
	sleep 1
done

# Step 7: Run tests
echo ""
echo "▶️  Running Playwright tests..."
echo ""
# Ensure we're in the project root (in case directory changed)
cd "$PROJECT_ROOT"
npx playwright test

echo ""
echo "✅ Complete test run finished!"

