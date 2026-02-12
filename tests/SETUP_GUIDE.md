# Test Setup Guide

This guide explains how to set up and run E2E tests for VelaChat.

## Philosophy

**Tests are DB-agnostic.** Tests don't know or care about database connection strings, clearing operations, or app lifecycle management. Tests only interact with the UI and assume:

- The app is running
- The database is in the expected state (empty for setup, or with existing data for regular tests)

**Infrastructure management is separate.** Database clearing and app lifecycle are handled by scripts, not by tests.

## Quick Start

### For Development (Fast Iteration)

When developing tests, you typically want to skip the setup and use existing data:

```bash
# 1. Make sure your app is running (in separate terminals):
#    Terminal 1: cd backend && conda activate velachat && ./dev.sh
#    Terminal 2: npm run dev

# 2. Run tests (skips setup):
SKIP_SETUP=true npm run test:e2e
```

### For Complete Test Run (Fresh Start)

When you want a clean slate (clears DB, runs setup, runs all tests):

```bash
ALLOW_DB_CLEAR=true npm run test:e2e:complete
```

**⚠️ WARNING:** This script performs destructive database operations. It requires `ALLOW_DB_CLEAR=true` as a safety measure.

## How It Works

### Setup Test (`tests/e2e/Setup.setup.ts`)

The setup test runs before all other tests (via Playwright project dependencies). It:

1. Goes through the onboarding flow (creates first admin user)
2. Configures initial settings (model connections, etc.)

**Assumptions:**

- App is already running
- Database is empty (only schema, no data)
- If users already exist, onboarding won't be shown and the test will fail (which is expected)

**Skipping Setup:**
Set `SKIP_SETUP=true` to skip the setup test when running tests:

```bash
SKIP_SETUP=true npm run test:e2e
```

### Complete Test Run Script (`scripts/complete_test_run.sh`)

This script handles the full lifecycle for a clean test run:

1. **Stops app** (if running) - kills uvicorn and vite processes
2. **Clears database** - truncates all tables (preserves schema and alembic state)
3. **Starts backend** - uses your existing `dev.sh` script
4. **Starts frontend** - runs `npm run dev`
5. **Waits for app** - verifies app is ready
6. **Runs tests** - executes Playwright tests (setup runs automatically)
7. **Cleans up** - stops app processes on exit

**Environment Variables:**

- `ALLOW_DB_CLEAR` - **Required.** Must be set to `"true"` to allow database clearing
- `DATABASE_URL` - PostgreSQL connection string (defaults to test DB)
- `PORT` - Backend server port (defaults to `8080`)
- `CONDA_ENV` - Conda environment name for backend (defaults to `"velachat"`)

**Usage:**

```bash
ALLOW_DB_CLEAR=true npm run test:e2e:complete
```

Or directly:

```bash
ALLOW_DB_CLEAR=true ./scripts/complete_test_run.sh
```

## Playwright Configuration

Tests use Playwright project dependencies to ensure setup runs first:

```typescript
// playwright.config.ts
projects: [
	{
		name: 'setup',
		testMatch: /.*\.setup\.ts/
	},
	{
		name: 'e2e',
		testMatch: /.*\.spec\.ts/,
		dependencies: ['setup'] // Setup runs first
	}
];
```

## Development Workflow

### Typical Development Session

1. **Start app manually** (you control when it starts/stops):

   ```bash
   # Terminal 1
   cd backend
   conda activate velachat  # or your conda env name
   ./dev.sh

   # Terminal 2
   npm run dev
   ```

2. **Develop tests** (fast iteration, uses existing data):

   ```bash
   SKIP_SETUP=true npm run test:e2e
   # or with UI mode
   SKIP_SETUP=true npm run test:e2e:ui
   ```

3. **When you want a clean run** (full setup + tests):
   ```bash
   ALLOW_DB_CLEAR=true npm run test:e2e:complete
   ```

### Why This Approach?

- **Safe:** Can't accidentally nuke your database (requires explicit env var)
- **Fast:** Skip setup when iterating on tests
- **Simple:** Tests don't manage infrastructure
- **Clear:** Separation of concerns (tests test, scripts manage infrastructure)

## CI/CD

In CI/CD, you typically:

1. Start fresh database
2. Start app (which will run migrations to init the db)
3. Run tests (setup runs automatically and before all other tests)

The setup test will handle onboarding and configuration. No need for `SKIP_SETUP` in CI.

## Troubleshooting

Note: The script sources your root-level `.env` file.

### "App failed to start"

- Check backend log: `tail -f /tmp/velachat-backend.log`
- Check frontend log: `tail -f /tmp/velachat-frontend.log`
- Verify database is accessible
- Verify ports `PORT` and 5173 are available

### "Database connection failed"

- Verify `DATABASE_URL` is set correctly
- Verify database is running
- Verify connection string format: `postgresql://user:pass@host:port/dbname`

### "Onboarding not shown" (setup test fails)

- Database already has users - this is expected if you're not using a clean DB
- Use `SKIP_SETUP=true` for development, or run `complete_test_run.sh` for clean run

### Tests fail with "user already exists"

- Tests should use unique identifiers (timestamps, UUIDs) for test data
