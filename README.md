# koggi
- PostgreSQL backup & restore CLI (early foundation).  



# Quick start

## 1. INSTALL  

```
pip install koggi
```

## 2. save settings in project root

```
# project-root/.env
KOGGI_DEFAULT_DB_NAME=db_name
KOGGI_DEFAULT_DB_USER=postgres
KOGGI_DEFAULT_DB_PASSWORD=password
KOGGI_DEFAULT_DB_HOST=localhost
KOGGI_DEFAULT_DB_PORT=5432
KOGGI_DEFAULT_SSL_MODE=prefer
KOGGI_DEFAULT_BACKUP_DIR=./backups
KOGGI_DEFAULT_ALLOW_RESTORE=true
```

## 3. download binary files  

```
koggi binaries download
```

## 4. backup

```
koggi pg backup
```

## 5. restore  

```
koggi pg restore
```



- Prepare a `.env` with at least one profile (DEFAULT example):

```
KOGGI_DEFAULT_DB_NAME=example
KOGGI_DEFAULT_DB_USER=postgres
KOGGI_DEFAULT_DB_PASSWORD=secret
KOGGI_DEFAULT_DB_HOST=localhost
KOGGI_DEFAULT_DB_PORT=5432
KOGGI_DEFAULT_SSL_MODE=prefer
KOGGI_DEFAULT_BACKUP_DIR=./backups
```

- `.env`  (dev1 example):

```
KOGGI_DEV1_DB_NAME=example
KOGGI_DEV1_DB_USER=postgres
KOGGI_DEV1_DB_PASSWORD=secret
KOGGI_DEV1_DB_HOST=localhost
KOGGI_DEV1_DB_PORT=5432
KOGGI_DEV1_SSL_MODE=prefer
KOGGI_DEV1_BACKUP_DIR=./backups
KOGGI_DEFAULT_ALLOW_RESTORE=false
```



- List profiles: `koggi config list`
- Test connection: `koggi config test DEFAULT`
- Create backup: `koggi pg backup -p DEFAULT`
- Restore latest: `koggi pg restore -p DEFAULT`
 - Check binaries: `koggi binaries which`

Notes

- Embedded binaries: Koggi can use packaged PostgreSQL tools.
  - Place binaries under `src/koggi/_bin/<os>-<arch>/`:
    - Example tags: `windows-x86_64`, `darwin-arm64`, `linux-x86_64`.
    - Required files: `pg_dump[.exe]`, `psql[.exe]`, `pg_restore[.exe]`.
  - Or put them in cache: `%LOCALAPPDATA%/koggi/bin/<tag>/` (Windows) or `~/.cache/koggi/bin/<tag>/` (Unix).
  - You can override via env: `KOGGI_PG_DUMP`, `KOGGI_PSQL`, `KOGGI_PG_RESTORE`.
- If no embedded binary is found, Koggi falls back to system PATH.
- This is Phase 1 scaffold based on plan.md; more features will follow.
