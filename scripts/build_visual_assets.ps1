[CmdletBinding()]
param(
    [string]$BrowserPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$guidePath = Join-Path $repoRoot 'source\guide.html'
$svgPath = Join-Path $repoRoot 'source\infographic.svg'
$pdfPath = Join-Path $repoRoot 'Claude-Code-Smart-Orchestrator-Kit.pdf'
$pngPath = Join-Path $repoRoot 'Claude-Code-Smart-Orchestrator-Infographic.png'

function Find-Browser {
    param([string]$RequestedPath)

    $candidates = @()
    if ($RequestedPath) { $candidates += $RequestedPath }

    foreach ($commandName in @('msedge.exe', 'chrome.exe')) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command) { $candidates += $command.Source }
    }

    $candidates += @(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe')
    )

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw 'No supported Chrome or Edge executable was found. Pass -BrowserPath with an installed browser path.'
}

function Convert-ToFileUri {
    param([string]$Path)
    return ([System.Uri]::new((Resolve-Path -LiteralPath $Path).Path)).AbsoluteUri
}

function Invoke-HeadlessBrowser {
    param(
        [string]$Browser,
        [string[]]$Arguments
    )

    $process = Start-Process `
        -FilePath $Browser `
        -ArgumentList $Arguments `
        -Wait `
        -PassThru `
        -WindowStyle Hidden

    if ($process.ExitCode -ne 0) {
        throw "Headless browser exited with code $($process.ExitCode)."
    }
}

function Get-PngDimensions {
    param([string]$Path)
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 24 -or $bytes[0] -ne 137 -or $bytes[1] -ne 80 -or $bytes[2] -ne 78 -or $bytes[3] -ne 71) {
        throw 'Generated infographic is not a valid PNG file.'
    }
    $widthBytes = [byte[]]@($bytes[19], $bytes[18], $bytes[17], $bytes[16])
    $heightBytes = [byte[]]@($bytes[23], $bytes[22], $bytes[21], $bytes[20])
    return [pscustomobject]@{
        Width = [System.BitConverter]::ToUInt32($widthBytes, 0)
        Height = [System.BitConverter]::ToUInt32($heightBytes, 0)
    }
}

foreach ($required in @($guidePath, $svgPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing visual source: $required"
    }
}

$browser = Find-Browser -RequestedPath $BrowserPath
$profileRoot = Join-Path $env:TEMP ("ccso-visual-build-{0}" -f [guid]::NewGuid().ToString('N'))
New-Item -Path $profileRoot -ItemType Directory -Force | Out-Null

try {
    $common = @(
        '--headless=new',
        '--disable-gpu',
        '--disable-extensions',
        '--disable-features=Translate',
        '--hide-scrollbars',
        '--no-first-run',
        '--no-pdf-header-footer',
        '--run-all-compositor-stages-before-draw',
        '--virtual-time-budget=2000',
        "--user-data-dir=`"$profileRoot`""
    )

    $guideUri = Convert-ToFileUri -Path $guidePath
    $pdfArguments = $common + @(
        "--print-to-pdf=`"$pdfPath`"",
        "`"$guideUri`""
    )
    Invoke-HeadlessBrowser -Browser $browser -Arguments $pdfArguments

    $svgUri = Convert-ToFileUri -Path $svgPath
    $pngArguments = $common + @(
        '--force-device-scale-factor=1',
        '--window-size=1600,2000',
        "--screenshot=`"$pngPath`"",
        "`"$svgUri`""
    )
    Invoke-HeadlessBrowser -Browser $browser -Arguments $pngArguments

    if (-not (Test-Path -LiteralPath $pdfPath -PathType Leaf) -or (Get-Item -LiteralPath $pdfPath).Length -lt 10000) {
        throw 'PDF output is missing or unexpectedly small.'
    }
    if (-not (Test-Path -LiteralPath $pngPath -PathType Leaf) -or (Get-Item -LiteralPath $pngPath).Length -lt 10000) {
        throw 'PNG output is missing or unexpectedly small.'
    }

    $pngSize = Get-PngDimensions -Path $pngPath
    if ($pngSize.Width -ne 1600 -or $pngSize.Height -ne 2000) {
        throw "Unexpected PNG dimensions: $($pngSize.Width)x$($pngSize.Height)."
    }

    $pdfHeader = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($pdfPath), 0, 5)
    if ($pdfHeader -ne '%PDF-') { throw 'Generated guide is not a valid PDF file.' }

    Write-Host "Browser: $browser"
    Write-Host "PDF: $pdfPath ($((Get-Item -LiteralPath $pdfPath).Length) bytes)"
    Write-Host "PNG: $pngPath ($($pngSize.Width)x$($pngSize.Height), $((Get-Item -LiteralPath $pngPath).Length) bytes)"
}
finally {
    if (Test-Path -LiteralPath $profileRoot) {
        $resolvedProfile = (Resolve-Path -LiteralPath $profileRoot).Path
        $resolvedTemp = (Resolve-Path -LiteralPath $env:TEMP).Path
        if ($resolvedProfile.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase) -and
            (Split-Path -Leaf $resolvedProfile).StartsWith('ccso-visual-build-', [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedProfile -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
