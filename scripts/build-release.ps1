param(
    [switch]$SkipChecks
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$web = Join-Path $repo "web"
$artifacts = Join-Path $repo "artifacts"
$stage = Join-Path $artifacts "stage"

Push-Location $repo
try {
    Remove-Item -LiteralPath (Join-Path $repo "build") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $repo "dist") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $artifacts -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $artifacts, $stage | Out-Null

    Push-Location $web
    try {
        npm.cmd ci
        npm.cmd run build
        npm.cmd audit --audit-level=high
    } finally {
        Pop-Location
    }

    if (-not $SkipChecks) {
        python scripts/check_repository_safety.py --history
        python -m compileall -q config connectors controllers database google_drive human_behavior models performance routing scripts services utils view views web_api main.py nlve_cli.py nlve_operator.py run.py
        python -m pytest -q -p no:cacheprovider
        python nlve_cli.py smoke
        python -m pip_audit -r requirements.txt
        python -m pip_audit -r requirements-dev.txt
        python -m pip_audit -r requirements-build.txt
    }

    python -m build
    python -m PyInstaller --noconfirm --clean nlvoorelkaar-reachout.spec

    $version = python -c "from config.version import __version__; print(__version__)"
    $releaseName = "NLvoorelkaar-Reachout-$version-Windows-x64"
    $releaseRoot = Join-Path $stage $releaseName
    New-Item -ItemType Directory -Force $releaseRoot | Out-Null
    Copy-Item -LiteralPath (Join-Path $repo "dist\NLvoorelkaar-Reachout") -Destination $releaseRoot -Recurse
    Copy-Item -LiteralPath (Join-Path $repo "dist\NLVE-Operator") -Destination $releaseRoot -Recurse
    Copy-Item -LiteralPath (Join-Path $repo "README.md") -Destination $releaseRoot
    Copy-Item -LiteralPath (Join-Path $repo "LICENSE") -Destination $releaseRoot
    Copy-Item -LiteralPath (Join-Path $repo "THIRD_PARTY_NOTICES.md") -Destination $releaseRoot
    Copy-Item -LiteralPath (Join-Path $repo "docs") -Destination (Join-Path $releaseRoot "docs") -Recurse
    $releaseScripts = Join-Path $releaseRoot "scripts"
    New-Item -ItemType Directory -Force $releaseScripts | Out-Null
    Copy-Item -LiteralPath (Join-Path $repo "scripts\start-web.ps1") -Destination $releaseScripts
    @"
This archive is an unsigned Windows build with GitHub artifact provenance.
Verify the adjacent SHA-256 file before use.
Code-signing remains required before broad third-party distribution.
"@ | Set-Content -LiteralPath (Join-Path $releaseRoot "RELEASE-STATUS.txt") -Encoding ascii

    $operator = Join-Path $releaseRoot "NLVE-Operator\NLVE-Operator.exe"
    & $operator smoke | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Packaged operator smoke test failed." }

    $sbom = Join-Path $artifacts "$releaseName.cdx.json"
    python -m cyclonedx_py requirements requirements.txt --output-format JSON --output-file $sbom
    $zip = Join-Path $artifacts "$releaseName.zip"
    Compress-Archive -LiteralPath $releaseRoot -DestinationPath $zip -CompressionLevel Optimal
    $hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([IO.Path]::GetFileName($zip))" | Set-Content -LiteralPath "$zip.sha256" -Encoding ascii
    Write-Output "Release archive: $zip"
} finally {
    Pop-Location
}
