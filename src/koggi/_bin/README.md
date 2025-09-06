# Embedded PostgreSQL Binaries

This directory contains platform-specific PostgreSQL client binaries that can be bundled with koggi packages.

## Directory Structure

```
_bin/
├── windows-x86_64/
│   ├── pg_dump.exe
│   ├── psql.exe
│   └── pg_restore.exe
├── linux-x86_64/
│   ├── pg_dump
│   ├── psql
│   └── pg_restore
├── darwin-x86_64/        # macOS Intel
│   ├── pg_dump
│   ├── psql
│   └── pg_restore
└── darwin-arm64/          # macOS Apple Silicon
    ├── pg_dump
    ├── psql
    └── pg_restore
```

## Usage

1. **For package maintainers**: Place the appropriate binaries in the correct platform subdirectory
2. **For users**: koggi will automatically detect and use these binaries if present
3. **Fallback**: If binaries aren't embedded, koggi can download them to cache or use system PATH

## Platform Tags

- `windows-x86_64`: Windows 64-bit
- `linux-x86_64`: Linux 64-bit  
- `darwin-x86_64`: macOS Intel 64-bit
- `darwin-arm64`: macOS Apple Silicon

## Binary Sources

PostgreSQL binaries should be obtained from official sources:
- Windows: [EnterpriseDB](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads)
- Linux: [PostgreSQL Official](https://www.postgresql.org/download/linux/)
- macOS: [PostgreSQL.app](https://postgresapp.com/) or Homebrew

## License Note

Embedded binaries must comply with PostgreSQL's license terms. This directory is included in the package build but is initially empty - binaries must be added separately by package maintainers.