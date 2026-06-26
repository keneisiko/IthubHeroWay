# Full backend audit: infra, env, management commands, API GET+POST smoke.
# Usage:
#   $env:API_BASE = "http://localhost:8000"
#   $env:API_LOGIN = "user@email"
#   $env:API_PASSWORD = "secret"
#   .\scripts\audit_backend.ps1

param(
    [string]$Base = $(if ($env:API_BASE) { $env:API_BASE } else { "http://localhost:8000" }),
    [string]$Login = $env:API_LOGIN,
    [string]$Password = $env:API_PASSWORD
)

$script:Failures = 0
$script:Warnings = 0

function Write-Pass { param([string]$Msg) Write-Host "  OK  $Msg" -ForegroundColor Green }
function Write-Fail { param([string]$Msg) Write-Host "  FAIL $Msg" -ForegroundColor Red; $script:Failures++ }
function Write-Warn { param([string]$Msg) Write-Host "  WARN $Msg" -ForegroundColor Yellow; $script:Warnings++ }
function Write-Section { param([string]$Title) Write-Host ""; Write-Host "== $Title ==" }

function Invoke-AuditHttp {
    param(
        [string]$Method,
        [string]$Path,
        [string]$Token = "",
        [string]$Body = $null
    )
    $headers = @{ "Content-Type" = "application/json" }
    if ($Token) { $headers["Authorization"] = "Bearer $Token" }
    $uri = "$Base$Path"
    try {
        if ($Method -eq "GET") {
            return Invoke-WebRequest -Uri $uri -Headers $headers -Method GET -UseBasicParsing -TimeoutSec 15
        }
        return Invoke-WebRequest -Uri $uri -Headers $headers -Method $Method -Body $Body -UseBasicParsing -TimeoutSec 15
    } catch {
        $status = $_.Exception.Response.StatusCode.value__
        return [PSCustomObject]@{ StatusCode = $status; Content = $_.ErrorDetails.Message }
    }
}

Write-Section "Docker containers"
try {
    $ps = docker compose ps 2>$null
    if ($ps -match "Up") { Write-Pass "docker compose services running" } else { Write-Warn "docker compose not fully up" }
} catch { Write-Warn "docker not available" }

Write-Section "Infra endpoints"
foreach ($path in @("/health/", "/ready/")) {
    try {
        $r = Invoke-AuditHttp -Method GET -Path $path
        $code = if ($r.StatusCode) { [int]$r.StatusCode } else { 0 }
        if ($code -eq 200) {
            $snippet = $r.Content
            if ($snippet.Length -gt 80) { $snippet = $snippet.Substring(0, 80) }
            Write-Pass "GET $path [$code] $snippet"
        } else { Write-Fail "GET $path [$code]" }
    } catch { Write-Fail "GET $path (error)" }
}

foreach ($path in @("/metrics/", "/schema/")) {
    try {
        $r = Invoke-WebRequest -Uri "$Base$path" -Method GET -UseBasicParsing -TimeoutSec 15
        if ($r.StatusCode -eq 200) { Write-Pass "GET $path [200]" } else { Write-Fail "GET $path [$($r.StatusCode)]" }
    } catch { Write-Fail "GET $path (error)" }
}

Write-Section "Environment variables (presence only)"
$envVars = @("DATABASE_URL", "REDIS_URL", "SECRET_KEY", "CELERY_BROKER_URL", "HIK_DATA_MODE", "LXP_VERIFY_URL", "LXP_API_TOKEN", "HIK_HOST", "TELEGRAM_BOT_TOKEN")
foreach ($v in $envVars) {
    if ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($v))) { Write-Warn "$v not set (may be ok in dev)" }
    else { Write-Pass "$v set" }
}

Write-Section "Management commands (--help)"
$mgmtCmds = @("import_lxp_students", "backfill_lxp_user_ids", "pull_lxp_performance", "sync_hik_events", "pull_hik_attendance", "fetch_hik_browser_export", "backfill_hik_card_codes", "verify_quests", "test_alert", "seed_demo_data")
foreach ($cmd in $mgmtCmds) {
    try {
        docker compose exec -T web python manage.py $cmd --help 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Pass "manage.py $cmd"; continue }
    } catch { }
    Write-Warn "manage.py $cmd unavailable"
}

Write-Section "Auth token"
$token = $null
if ($Login -and $Password) {
    try {
        $loginBody = @{ login = $Login; password = $Password } | ConvertTo-Json
        $loginResp = Invoke-RestMethod -Uri "$Base/api/v1/auth/login/" -Method POST -Body $loginBody -ContentType "application/json" -TimeoutSec 15
        $token = $loginResp.access
        if ($token) { Write-Pass "LXP login token acquired" }
    } catch { Write-Warn "LXP login failed; trying JWT create" }

    if (-not $token) {
        try {
            $jwtBody = @{ username = $Login; password = $Password } | ConvertTo-Json
            $jwtResp = Invoke-RestMethod -Uri "$Base/api/v1/auth/jwt/create/" -Method POST -Body $jwtBody -ContentType "application/json" -TimeoutSec 15
            $token = $jwtResp.access
            if ($token) { Write-Pass "JWT create token acquired" } else { Write-Fail "Could not obtain auth token" }
        } catch { Write-Fail "Could not obtain auth token" }
    }
} else {
    Write-Warn "No API_LOGIN/API_PASSWORD - skipping authenticated API checks"
}

function Test-ApiGet {
    param([string]$Path, [string]$Token)
    $r = Invoke-AuditHttp -Method GET -Path $Path -Token $Token
    $code = if ($r.StatusCode) { [int]$r.StatusCode } else { 0 }
    if ($code -ge 200 -and $code -lt 300) { Write-Pass "GET $Path [$code]" } else { Write-Fail "GET $Path [$code]" }
}

function Test-ApiPost {
    param([string]$Path, [string]$Body, [string]$Token, [int[]]$OkCodes = @(200, 201, 400, 404, 429))
    $r = Invoke-AuditHttp -Method POST -Path $Path -Token $Token -Body $Body
    $code = if ($r.StatusCode) { [int]$r.StatusCode } else { 0 }
    if ($OkCodes -contains $code) { Write-Pass "POST $Path [$code]" } else { Write-Fail "POST $Path [$code]" }
}

if ($token) {
    Write-Section "API GET smoke"
    $getPaths = @(
        '/api/v1/dashboard/',
        '/api/v1/profile/me/',
        '/api/v1/profile/me/characteristics/',
        '/api/v1/rating/me/',
        '/api/v1/rating/history/',
        '/api/v1/leaderboard/agents/?page=1&page_size=20',
        '/api/v1/squads/me/',
        '/api/v1/squads/',
        '/api/v1/squads/leaderboard/?limit=10',
        '/api/v1/quests/active/',
        '/api/v1/quests/my-progress/?completed=false',
        '/api/v1/quests/rewards/history/',
        '/api/v1/shop/items/',
        '/api/v1/shop/my-purchases/',
        '/api/v1/badges/my/',
        '/api/v1/badges/'
    )
    foreach ($p in $getPaths) { Test-ApiGet -Path $p -Token $token }

    Write-Section "API POST smoke (non-destructive where possible)"
    Test-ApiPost -Path "/api/v1/auth/jwt/refresh/" -Body '{"refresh":"invalid"}' -Token $token -OkCodes @(401, 400)
    Test-ApiPost -Path "/api/v1/social/respects/" -Body '{"to_username":"nonexistent_user_xyz"}' -Token $token
    Test-ApiPost -Path "/api/v1/social/duels/" -Body '{"opponent_username":"nonexistent_user_xyz"}' -Token $token
    Test-ApiPost -Path "/api/v1/social/mentorships/" -Body '{"mentee_username":"nonexistent_user_xyz"}' -Token $token
}

Write-Section "Summary"
Write-Host "Failures: $Failures  Warnings: $Warnings"
if ($Failures -gt 0) { exit 1 }
Write-Host "Backend audit passed (critical checks)."
exit 0
