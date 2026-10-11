# Makes redacted copies of the AWS console screenshots for the video.
# Originals in assets/aws/ are never modified. Redaction uses solid opaque
# boxes (not blur) over the account menu (name + 12-digit account ID) and any
# ARN that embeds the account ID. Output: public/aws/ (git-ignored).
# Usage (from video/): powershell -NoProfile -File scripts/redact-aws.ps1

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$src = Join-Path $PSScriptRoot '..\assets\aws'
$dst = Join-Path $PSScriptRoot '..\public\aws'
New-Item -ItemType Directory -Force $dst | Out-Null

# Account menu (top right) appears on every console page.
$accountMenu = @(1612, 104, 293, 58)

$jobs = @(
  @{ In = 'A1 — CloudFormation stacks.png';         Out = 'A1-cloudformation-stacks.png';    Boxes = @() },
  @{ In = 'A2 — Stack resources.png';               Out = 'A2-cloudformation-resources.png'; Boxes = @() },
  @{ In = 'A3 — Lambda functions.png';              Out = 'A3-lambda-functions.png';         Boxes = @() },
  @{ In = 'A4 — Lambda configuration.png';          Out = 'A4-lambda-configuration.png';     Boxes = @(,@(1020, 350, 455, 56)) },
  @{ In = 'A5 — API routes.png';                    Out = 'A5-api-routes.png';               Boxes = @() },
  @{ In = 'A6 — DynamoDB cache item.png';           Out = 'A6-dynamodb-cache-item.png';      Boxes = @() },
  @{ In = 'A7 — CloudFront origin.png';             Out = 'A7-cloudfront-origin.png';        Boxes = @(,@(1160, 380, 318, 58)) },
  @{ In = 'A8 — S3 public-access protection.png';   Out = 'A8-s3-public-access.png';         Boxes = @() }
)

$fill = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 15, 20, 26))
$textBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 140, 150, 160))
$font = New-Object System.Drawing.Font('Segoe UI', 13)

foreach ($job in $jobs) {
  $inPath = Join-Path $src $job.In
  if (-not (Test-Path -LiteralPath $inPath)) { throw "Missing screenshot: $($job.In)" }
  $img = [System.Drawing.Image]::FromFile((Resolve-Path -LiteralPath $inPath))
  $bmp = New-Object System.Drawing.Bitmap $img
  $img.Dispose()
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias
  foreach ($b in (@(,$accountMenu) + $job.Boxes)) {
    $g.FillRectangle($fill, $b[0], $b[1], $b[2], $b[3])
    $g.DrawString('redacted', $font, $textBrush, $b[0] + 10, $b[1] + ($b[3] / 2) - 11)
  }
  $g.Dispose()
  $outPath = Join-Path $dst $job.Out
  $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Write-Output "redacted -> $($job.Out)"
}
