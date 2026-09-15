# Windows: тот же scripts/init_postgres.sql, что Linux/macOS.
# Запуск из корня репозитория:
#   powershell -ExecutionPolicy Bypass -File scripts\init_postgres.ps1
# Если спросит пароль — это пароль суперпользователя postgres (задавали при установке).
# Либо заранее: $env:PGPASSWORD = "ваш_пароль_postgres"

$ErrorActionPreference = "Stop"
$Sql = Join-Path $PSScriptRoot "init_postgres.sql"

function Find-Psql {
    $cmd = Get-Command psql -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $versions = @("16", "15", "14", "17", "13")
    foreach ($v in $versions) {
        $candidate = "C:\Program Files\PostgreSQL\$v\bin\psql.exe"
        if (Test-Path $candidate) { return $candidate }
    }
    throw "psql не найден. Установите PostgreSQL и добавьте bin в PATH (например C:\Program Files\PostgreSQL\16\bin)."
}

$Psql = Find-Psql
Write-Host "Using: $Psql"
& $Psql -U postgres -d postgres -v ON_ERROR_STOP=1 -f $Sql
if ($LASTEXITCODE -ne 0) {
    throw "psql exited with code $LASTEXITCODE"
}
Write-Host "OK: library_db / library_user"
