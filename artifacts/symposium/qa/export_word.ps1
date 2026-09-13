param([string]$Stem = 'RoomBridge_Symposium_Abstract')
$ErrorActionPreference = 'Stop'
$docxPath = (Resolve-Path "$PSScriptRoot/../$Stem.docx").Path
$pdfPath = Join-Path $PSScriptRoot "$Stem.pdf"
$wordApp = New-Object -ComObject Word.Application
$wordApp.Visible = $false
$wordApp.DisplayAlerts = 0
$wordDoc = $null
try {
    $wordDoc = $wordApp.Documents.Open($docxPath, $false, $true)
    $wordDoc.Repaginate()
    Write-Output "Word count: $($wordDoc.ComputeStatistics(0))"
    Write-Output "Page count: $($wordDoc.ComputeStatistics(2))"
    $wordDoc.ExportAsFixedFormat($pdfPath, 17)
} finally {
    if ($null -ne $wordDoc) { $wordDoc.Close(0) }
    $wordApp.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) | Out-Null
}
