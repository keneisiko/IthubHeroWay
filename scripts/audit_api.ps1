# Smoke-test Hero Path API endpoints used by the frontend.
# Usage:
#   $env:API_BASE = "http://localhost:8000"
#   $env:API_LOGIN = "your@email"
#   $env:API_PASSWORD = "secret"
#   .\scripts\audit_api.ps1

param(
    [string]$Base = $(if ($env:API_BASE) { $env:API_BASE } else { "http://localhost:8000" }),
    [string]$Login = $env:API_LOGIN,
    [string]$Password = $env:API_PASSWORD
)

if (-not $Login -or -not $Password) {
    Write-Error "Set API_LOGIN and API_PASSWORD environment variables."
    exit 1
}

function Invoke-AuditRequest {
    param(
        [string]$Method,
        [string]$Path,
        [string]$Token,
        [string]$Body = $null
    )
    $headers = @{
        Authorization = "Bearer $Token"
        "Content-Type" = "application/json"
    }
    $uri = "$Base$Path"
    try {
        if ($Method -eq "GET") {
            $resp = Invoke-WebRequest -Uri $uri -Headers $headers -Method GET -UseBasicParsing
        } else {
            $resp = Invoke-WebRequest -Uri $uri -Headers $headers -Method $Method -Body $Body -UseBasicParsing
        }
        $snippet = $resp.Content
        if ($snippet.Length -gt 160) { $snippet = $snippet.Substring(0, 160) + "..." }
        Write-Host "[$($resp.StatusCode)] $Method $Path"
        Write-Host $snippet
    } catch {
        $status = $_.Exception.Response.StatusCode.value__
        Write-Host "[$status] $Method $Path (error)"
    }
    Write-Host ""
}

Write-Host "== Login =="
$loginBody = @{ login = $Login; password = $Password } | ConvertTo-Json
$loginResp = Invoke-RestMethod -Uri "$Base/api/v1/auth/login/" -Method POST -Body $loginBody -ContentType "application/json"
$token = $loginResp.access
if (-not $token) {
    Write-Error "Login failed"
    exit 1
}
Write-Host "Token acquired."
Write-Host ""

Write-Host "== Dashboard & profile =="
Invoke-AuditRequest -Method GET -Path "/api/v1/dashboard/" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/profile/me/" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/profile/me/characteristics/" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/rating/me/" -Token $token

Write-Host "== Leaderboard & squads =="
Invoke-AuditRequest -Method GET -Path "/api/v1/leaderboard/agents/?page=1&page_size=20" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/leaderboard/agents/?page=1&page_size=20&track=dev-backend" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/leaderboard/agents/?page=1&page_size=20&search=demo" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/squads/me/" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/squads/" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/squads/leaderboard/?limit=10" -Token $token

Write-Host "== Quests & shop =="
Invoke-AuditRequest -Method GET -Path "/api/v1/quests/active/" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/quests/my-progress/?completed=false" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/quests/rewards/history/" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/shop/items/" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/shop/my-purchases/" -Token $token

Write-Host "== Badges =="
Invoke-AuditRequest -Method GET -Path "/api/v1/badges/my/" -Token $token
Invoke-AuditRequest -Method GET -Path "/api/v1/badges/" -Token $token

Write-Host "Done."
