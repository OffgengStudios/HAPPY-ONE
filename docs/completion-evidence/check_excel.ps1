$ErrorActionPreference = 'Stop'
$excel = $null
$safeBook = $null
$controlBook = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    $controlBook = $excel.Workbooks.Open((Join-Path $PSScriptRoot 'unsafe-control.csv'), 0, $true, 2)
    $controlFormula = [bool]$controlBook.Worksheets.Item(1).Cells.Item(2, 3).HasFormula
    if (-not $controlFormula) { throw 'The control did not use normal formula interpretation.' }
    $controlBook.Close($false)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($controlBook)
    $controlBook = $null
    $safeBook = $excel.Workbooks.Open((Join-Path $PSScriptRoot 'safe-export.csv'), 0, $true, 2)
    $sheet = $safeBook.Worksheets.Item(1)
    $rows = [int]$sheet.UsedRange.Rows.Count
    if ($rows -ne 11) { throw 'Unexpected number of CSV rows.' }
    if ([int]$sheet.UsedRange.Columns.Count -ne 7) { throw 'Unexpected CSV column parsing.' }
    $formulas = 0
    for ($i = 2; $i -le $rows; $i++) {
        if ($sheet.Cells.Item($i, 3).HasFormula) { $formulas++ }
    }
    if ($formulas -ne 0) { throw 'A protected text cell was interpreted as a formula.' }
    if ([double]$sheet.Cells.Item(2, 6).Value2 -ne -12.5) { throw 'Negative numeric value changed.' }
    $result = @{
        application = 'Microsoft Excel'
        version = [string]$excel.Version
        unsafe_control_has_formula = $controlFormula
        protected_text_cells = $rows - 1
        protected_formula_count = $formulas
        negative_numeric_value = [double]$sheet.Cells.Item(2, 6).Value2
        negative_numeric_type = [string]$sheet.Cells.Item(2, 6).Value2.GetType().FullName
        general_csv_import = $true
        forced_text_columns = $false
    }
    $safeBook.Close($false)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($sheet)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($safeBook)
    $safeBook = $null
    $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'evidence/csv-excel.json')
    $result | ConvertTo-Json
} finally {
    if ($null -ne $controlBook) { $controlBook.Close($false) }
    if ($null -ne $safeBook) { $safeBook.Close($false) }
    if ($null -ne $excel) {
        $excel.Quit()
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
