# Auto-generate and fix Alembic migration (PowerShell)
# Usage: .\scripts\alembic_autofix.ps1 "migration_description"

param(
    [Parameter(Mandatory=$true)]
    [string]$Message
)

# Generate migration
alembic revision --autogenerate -m $Message

# Get the latest migration file
$LatestMigration = Get-ChildItem -Path "db_migrations\versions\*.py" | 
    Sort-Object LastWriteTime -Descending | 
    Select-Object -First 1

# Check if it's an initial migration
$content = Get-Content $LatestMigration.FullName -Raw
if ($content -match "down_revision = None") {
    Write-Host "Initial migration detected - auto-fixing..." -ForegroundColor Yellow
    python scripts/fix_alembic_migration.py $LatestMigration.FullName --initial
} else {
    Write-Host "Regular migration - fixing common issues..." -ForegroundColor Yellow
    python scripts/fix_alembic_migration.py $LatestMigration.FullName
}

Write-Host "✓ Migration generated and fixed: $($LatestMigration.Name)" -ForegroundColor Green
