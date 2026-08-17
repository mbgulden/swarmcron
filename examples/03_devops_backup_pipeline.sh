#!/usr/bin/env bash
# examples/03_devops_backup_pipeline.sh
# Demonstrates CLI automation, store isolation, crontab export, and recovery with SwarmCron.

set -e

# Ensure ~/.local/bin is in PATH for user-installed CLI
export PATH="$HOME/.local/bin:$PATH"

STORE_PATH="/tmp/swarmcron_devops.json"
echo "======================================================================"
echo "🛠️ SwarmCron DevOps Automation & Crontab Pipeline"
echo "======================================================================"

# 1. Register Database Dump Task
echo -e "\n📦 1. Registering Database Dump Task..."
swarmcron --store "$STORE_PATH" register \
  --id "db-backup" \
  --name "Nightly Database Dump" \
  --schedule "0 2 * * *" \
  --command "python3 -c \"print('Exported pg_dump (42MB) to /tmp/db.sql')\"" \
  --group "infrastructure" \
  --tags "db,critical"

# 2. Register S3 Sync Task (Depends on DB Dump)
echo -e "\n☁️ 2. Registering S3 Sync Task (with DAG dependency)..."
swarmcron --store "$STORE_PATH" register \
  --id "s3-sync" \
  --name "Offsite S3 Replication" \
  --schedule "15 2 * * *" \
  --command "python3 -c \"print('Uploaded /tmp/db.sql to s3://company-backups/2026/db.sql')\"" \
  --depends-on "db-backup" \
  --group "infrastructure" \
  --tags "s3,storage"

# 3. Export Crontab Lines
echo -e "\n🐧 3. Exporting System Crontab..."
swarmcron --store "$STORE_PATH" export-crontab --include-header

# 4. Trigger Execution
echo -e "\n🚀 4. Triggering Database Backup via CLI..."
swarmcron --store "$STORE_PATH" run "db-backup"

# 5. Trigger Downstream S3 Sync
echo -e "\n🚀 5. Triggering Downstream S3 Sync..."
swarmcron --store "$STORE_PATH" run "s3-sync"

# 6. Replay Recovery
echo -e "\n🔄 6. Running Replay Recovery on S3 Sync..."
swarmcron --store "$STORE_PATH" recover "s3-sync" --max-retries 2

echo -e "\n======================================================================"
echo "✅ DevOps Pipeline Complete!"
echo "======================================================================"
