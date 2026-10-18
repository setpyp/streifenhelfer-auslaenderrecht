# Erzeugt die App-Icons (app/icon-*.png): blaues Quadrat mit Paragrafenzeichen.
Add-Type -AssemblyName System.Drawing
$out = Join-Path $PSScriptRoot "..\app"
foreach ($size in 180, 192, 512) {
    $bmp = New-Object System.Drawing.Bitmap $size, $size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = "AntiAlias"; $g.TextRenderingHint = "AntiAliasGridFit"
    $g.Clear([System.Drawing.Color]::FromArgb(11, 42, 74))
    $font = New-Object System.Drawing.Font "Segoe UI", ([single]($size * 0.58)), ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
    $fmt = New-Object System.Drawing.StringFormat
    $fmt.Alignment = "Center"; $fmt.LineAlignment = "Center"
    $rect = New-Object System.Drawing.RectangleF 0, ([single]($size * 0.03)), $size, $size
    $g.DrawString([string][char]0x00A7, $font, [System.Drawing.Brushes]::White, $rect, $fmt)
    $bmp.Save((Join-Path $out "icon-$size.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
}
