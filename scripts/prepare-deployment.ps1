$ErrorActionPreference = 'Stop'
$deployment = Split-Path -Parent $PSScriptRoot

function Copy-Example([string] $path) {
    $example = "$path.example"
    if ((Test-Path -LiteralPath $example) -and -not (Test-Path -LiteralPath $path)) {
        Copy-Item -LiteralPath $example -Destination $path
    }
}

Copy-Example (Join-Path $deployment '.env')
Get-ChildItem -LiteralPath (Join-Path $deployment 'envs') -Recurse -File -Filter '*.env.example' |
    ForEach-Object {
        $target = $_.FullName.Substring(0, $_.FullName.Length - '.example'.Length)
        Copy-Example $target
    }

Write-Host 'Deployment templates prepared. Edit deployment/.env before starting Dify.'

