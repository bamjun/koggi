# koggi

PostgreSQL backup & restore CLI (early foundation).

Quick start

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
```



- List profiles: `koggi config list`
- Test connection: `koggi config test DEFAULT`
- Create backup: `koggi pg backup -p DEFAULT`
- Restore latest: `koggi pg restore -p DEFAULT`

Notes

- Requires PostgreSQL client tools in PATH: `pg_dump`, `psql`, `pg_restore`.
- Passwords are read from env (`KOGGI_<PROFILE>_DB_PASSWORD`) for now.
- This is Phase 1 scaffold based on plan.md; more features will follow.
