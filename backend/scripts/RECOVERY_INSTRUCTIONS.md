# Image Recovery Instructions

(this was written by AI but I verified that it works)

## Background

Due to a migration bug, in-chat images were stored in a non-persisted directory (not in Docker volumes) and were lost after container restarts. This document explains how to recover these images from a backup database dump.

## Prerequisites

1. A backup database dump from before the migration (one still containing the base64-encoded images)
2. Access to both the backup database and the current production database
3. Ability to run commands inside the Docker container or with database access

## Step 1: Restore Backup Database

First, you need to restore your backup dump to a temporary database. You can either:

### Option A: Restore to a separate database on the same PostgreSQL server

```bash
# Create a temporary database
PGPASSWORD="$PG_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "CREATE DATABASE backup_recovery_temp;"

# Restore the dump
PGPASSWORD="$PG_PASSWORD" pg_restore -h "$DB_HOST" -U "$DB_USER" -d backup_recovery_temp -F c -v backup.dump
```

### Option B: Restore to a separate PostgreSQL instance

If you have a separate PostgreSQL instance available, restore there:

```bash
PGPASSWORD="$BACKUP_PASSWORD" pg_restore -h "$BACKUP_HOST" -U "$BACKUP_USER" -d backup_recovery_temp -F c -v backup.dump
```

## Step 2: Test the Recovery Script (Dry Run)

**ALWAYS run a dry run first** to see what will be recovered without making any changes:

```bash
# Inside Docker container (script should be at /app/backend/scripts/recover_lost_images.py)
docker exec -it open-webui-openwebui-1 python /app/backend/scripts/recover_lost_images.py \
  --backup-db-url "postgresql://dev:password@host.docker.internal:10865/backup_recovery_temp" \
  --dry-run

# If script isn't in the image yet, copy it first:
docker cp backend/scripts/recover_lost_images.py open-webui-openwebui-1:/app/backend/scripts/

# Or from host (if you have database access)
python backend/scripts/recover_lost_images.py \
  --backup-db-url "postgresql://dev:password@host.docker.internal:10865/backup_recovery_temp" \
  --current-db-url "postgresql://user:password@host:5432/current_db" \
  --dry-run
```

The script will:

- Connect to both databases
- Find all base64 images in the backup
- Match them to current database records
- Show what would be recovered (without actually doing it)

## Step 3: Run the Actual Recovery

Once you've verified the dry run looks correct, run the actual recovery:

```bash
# Inside Docker container
docker exec -it open-webui python /app/backend/scripts/recover_lost_images.py \
  --backup-db-url "postgresql://user:password@host:5432/backup_recovery_temp"

# If script isn't in the image yet, copy it first:
docker cp backend/scripts/recover_lost_images.py open-webui:/app/backend/scripts/

# Or from host
python backend/scripts/recover_lost_images.py \
  --backup-db-url "postgresql://user:password@host:5432/backup_recovery_temp" \
  --current-db-url "postgresql://user:password@host:5432/current_db"
```

The script will:

1. Extract base64 images from chat JSON blobs in the backup
2. Match them to `chat_message_attachment` records in the current database
3. Recreate the files in the correct location (`/app/backend/data/uploads/` - persisted in Docker volume)
4. Update or create file records in the database

## Step 4: Verify Recovery

After running the recovery:

1. Check that files were created:

   ```bash
   docker exec -it open-webui ls -lh /app/backend/data/uploads/
   ```

2. Check a few chats in the UI to see if images are now visible

3. Check the database to verify file records:
   ```bash
   docker exec -it open-webui python -c "
   from open_webui.internal.db import get_db
   from sqlalchemy import text
   with get_db() as db:
       result = db.execute(text('SELECT COUNT(*) FROM file WHERE meta::text LIKE \\'%\"image\": true%\\''))
       print(f'Total image files: {result.scalar()}')
   "
   ```

## Step 5: Clean Up

After successful recovery, you can drop the temporary backup database:

```bash
PGPASSWORD="$PG_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "DROP DATABASE backup_recovery_temp;"
```

## Troubleshooting

### "No matching attachment found"

This means the script couldn't find a `chat_message_attachment` record in the current database that corresponds to the image in the backup. This could happen if:

- The chat/message was deleted after migration
- The migration didn't create the attachment record properly
- The message_id doesn't match

The script will skip these images. You may need to manually investigate these cases.

### "File record exists but file missing on disk"

This is expected - it means the file record was created during migration but the file was lost. The script will recreate it.

### "DATABASE_URL environment variable not set"

Make sure you either:

- Set the `DATABASE_URL` environment variable, or
- Use the `--current-db-url` argument

### Permission errors writing files

Make sure the Docker volume is properly mounted and writable:

```bash
docker exec -it open-webui touch /app/backend/data/uploads/.test_write
```

## How the Script Works

1. **Extraction**: Reads all chats from the backup database and extracts base64 images from the `chat` JSON blob
2. **Matching**: For each image, finds the corresponding `chat_message_attachment` record in the current database by matching `chat_id` and `message_id`
3. **File Creation**: Decodes the base64 image, calculates its hash, and writes it to `/app/backend/data/uploads/` (the persisted volume)
4. **Database Update**: Updates the file record with the correct path, or creates a new file record if one doesn't exist

## Notes

- The script uses hash-based deduplication - if the same image appears multiple times, it will reuse the same file
- Files are stored with their SHA-256 hash as the filename for easy deduplication
- The script is idempotent - you can run it multiple times safely
- Only images that can be matched to existing `chat_message_attachment` records will be recovered

## Data Loss Incident

This recovery is necessary due to a bug in migrations `9f0b_backfill_chat_messages.py` and `9f0d_migrate_base64_images.py` that stored files in a non-persisted directory. The migrations have been fixed to use the same robust path resolution as `9f0c_migrate_model_images.py` (which correctly uses Docker volumes).

If you're affected by this issue and don't have a backup, unfortunately the images cannot be recovered as they were stored in ephemeral container storage that was lost on restart.
