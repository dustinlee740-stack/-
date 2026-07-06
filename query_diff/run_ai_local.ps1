<#
  run_ai_local.ps1 — 개인·로컬 AI 비교 런처 (구독 claude -p 경로)

  ANTHROPIC_API_KEY 를 제거해 구독으로 강제(설정돼 있으면 metered 과금)하고, AI 비교용 env 를
  세팅한 뒤 로컬 uvicorn 을 기동한다. 서버 배포 불필요 — 본인 PC에서만.

  사용:  .\run_ai_local.ps1            # 기본 포트 8000
         .\run_ai_local.ps1 -Port 9000
#>
param(
  [int]$Port = 8000
)

# 구독 강제: API 키가 있으면 claude -p 가 metered 로 청구됨 → 이 셸에서 제거.
if ($env:ANTHROPIC_API_KEY) {
  Write-Host "ANTHROPIC_API_KEY 감지 → 제거(구독으로 강제, metered 과금 방지)" -ForegroundColor Yellow
}
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue

# 기본값(이미 설정돼 있으면 사용자 값을 존중)
if (-not $env:QD_AI_MODEL)   { $env:QD_AI_MODEL = "claude-sonnet-5" }
if (-not $env:QD_AI_TIMEOUT) { $env:QD_AI_TIMEOUT = "420" }
# ODS 정의 SQL 폴더(있으면 ods.* 집계 정의를 Python이 선로딩해 Claude에 제공)
if (-not $env:QD_ODS_DIR -and (Test-Path "D:\da\ttp_workflow\ODS")) { $env:QD_ODS_DIR = "D:\da\ttp_workflow\ODS" }

Set-Location $PSScriptRoot

# claude CLI 확인(없어도 계속 — 그 경우 AI 버튼은 LIMITED 로 표시됨)
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host "경고: 'claude' CLI 를 PATH 에서 찾지 못했습니다. AI 비교는 LIMITED 로 표시됩니다." -ForegroundColor Yellow
  Write-Host "      설치 후 'claude' -> /login 으로 구독 로그인이 필요합니다." -ForegroundColor Yellow
}

Write-Host "--------------------------------------------------" -ForegroundColor DarkGray
Write-Host " query_diff 로컬 서버 (AI 비교 = claude -p 구독 경로)" -ForegroundColor Cyan
Write-Host "  model   : $env:QD_AI_MODEL"
Write-Host "  timeout : $env:QD_AI_TIMEOUT s"
Write-Host "  ODS dir : $(if ($env:QD_ODS_DIR) { $env:QD_ODS_DIR } else { '(미설정 — ODS 선로딩 off)' })"
Write-Host "  url     : http://127.0.0.1:$Port"
Write-Host "  확인    : 다른 셸에서 'claude' -> /status 로 구독 로그인(ANTHROPIC_API_KEY 미표시) 확인" -ForegroundColor DarkGray
Write-Host "--------------------------------------------------" -ForegroundColor DarkGray

python -m uvicorn query_diff.api:app --port $Port
