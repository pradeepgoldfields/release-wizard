---
name: seed
description: Re-seed the Conduit development database with representative data. Resets the instance database, runs seed_data.py, and verifies the server starts cleanly.
argument-hint: "[reset|append]"
---

# Seed Database — Conduit

Mode: **$ARGUMENTS** (defaults to `reset`)

## reset — Drop and recreate everything

```bash
# 1. Stop any running server
powershell -Command "Get-NetTCPConnection -LocalPort 8080 -EA SilentlyContinue | %{ Stop-Process -Id \$_.OwningProcess -Force -EA SilentlyContinue }"

# 2. Remove existing database
rm -f instance/release_wizard.db instance/conduit.db

# 3. Activate venv
source venv/Scripts/activate

# 4. Run seed script (creates tables + sample data)
python scripts/seed_data.py

# 5. Verify server starts
python wsgi.py &
sleep 3
curl -sf http://localhost:8080/healthz && echo "✅ Server healthy after seed" || echo "❌ Server failed to start"
```

## append — Add seed data to existing database

```bash
source venv/Scripts/activate
python scripts/seed_data.py
```

The seed script is idempotent — it skips records that already exist (checks by name/key).

## Verify key data was created

```bash
# Check products exist
curl -s http://localhost:8080/api/v1/products \
  -H "Authorization: Bearer $(curl -s -X POST http://localhost:8080/api/v1/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"username":"admin","password":"admin"}' | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')" \
  | python -c "import sys,json; d=json.load(sys.stdin); print(f'✅ {d[\"meta\"][\"total\"]} products seeded')"

# Check agent pools
curl -s http://localhost:8080/api/v1/agent-pools | python -c "import sys,json; pools=json.load(sys.stdin); print(f'✅ {len(pools)} agent pools seeded')"
```

Report the number of products, pipelines, users, and agent pools created.
