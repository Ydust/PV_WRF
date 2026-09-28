param([switch]$KeyYearsOnly,[switch]$Resume,[string]$InputName='greet_case_inputs.json',[string]$ResultName='greet_case_results')
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$greetRoot=Join-Path $taskRoot 'input\GREET_2025_Rev1'
$config=Get-Content -LiteralPath (Join-Path $taskRoot ('input\inventory\'+$InputName)) -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path (Join-Path $taskRoot 'output\inventory') | Out-Null
$excel=$null;$energy=$null;$materials=$null
function Read-CellValue($worksheet,[string]$address){
    for($readAttempt=0;$readAttempt -lt 12;$readAttempt++){
        try{return $worksheet.Range($address).Value2}
        catch{
            if($_.Exception.HResult -ne -2147418111 -or $readAttempt -eq 11){throw}
            Start-Sleep -Milliseconds 500
        }
    }
}
try {
    $excel=New-Object -ComObject Excel.Application
    $excel.Visible=$false;$excel.DisplayAlerts=$false;$excel.EnableEvents=$false
    # The official GREET calculation functions require trusted VBA execution.
    $excel.AutomationSecurity=1;$excel.AskToUpdateLinks=$false
    $energy=$excel.Workbooks.Open((Join-Path $greetRoot 'R&D GREET1_2025_Rev1.xlsm'),0,$true)
    $materials=$excel.Workbooks.Open((Join-Path $greetRoot 'R&D GREET2_2025_Rev1.xlsm'),0,$true)
    foreach($link in @($materials.LinkSources(1))){$materials.ChangeLink($link,$energy.FullName,1)}
    $excel.Calculation=-4135
    $e=$energy.Worksheets.Item('Electric');$m=$materials.Worksheets.Item('Mat_Inputs');$pv=$materials.Worksheets.Item('Solar_PV')
    $e.Range('A15').Value2='Yes'
    $results=@()
    $partialPath=Join-Path $taskRoot ('output\inventory\'+$ResultName+'.partial.json')
    if($Resume -and (Test-Path -LiteralPath $partialPath)){
        $results=@(Get-Content -LiteralPath $partialPath -Raw | ConvertFrom-Json)
    }
    Write-Output 'Models opened and linked; power-generation infrastructure included.'
    foreach($case in $config.cases){
        if($KeyYearsOnly -and $case.production_year -notin @(2025,2030,2050)){continue}
        if(@($results | Where-Object {$_.case -eq $case.case -and $_.production_year -eq $case.production_year}).Count -gt 0){continue}
        foreach($change in $case.changes){
            $sheet=if($change[0] -eq 'energy'){$e}else{$m}
            for($writeAttempt=0;$writeAttempt -lt 12;$writeAttempt++){
                try{$sheet.Range([string]$change[2]).Value2=[double]$change[3];break}
                catch{
                    if($_.Exception.HResult -ne -2147418111 -or $writeAttempt -eq 11){throw}
                    Start-Sleep -Milliseconds 500
                }
            }
        }
        $excel.CalculateFull()
        # GREET's calculation functions can leave follow-on dependencies dirty.
        # In manual mode xlPending (2) does not progress by waiting alone.
        if($excel.CalculationState -eq 2){$excel.Calculate()}
        $timer=[Diagnostics.Stopwatch]::StartNew()
        while($excel.CalculationState -eq 1){
            if($timer.Elapsed.TotalSeconds -gt 60){throw 'Calculation did not finish within 60 seconds'}
            Start-Sleep -Milliseconds 200
        }
        $record=[ordered]@{case=$case.case;production_year=$case.production_year;additional_wind_procurement=$case.additional_wind_procurement}
        foreach($address in @('BV476','CG476','CI476','CM476','D209','B254','B54','B66','B90','B106','D157','D161','D579','EE289','EC289','ED289','EG289','EF289','DR289','DX289','BV446','CI423','DR289','BV417')){
            $value=Read-CellValue $pv $address
            for($attempt=0; $attempt -lt 2 -and ($null -eq $value -or $value -is [string] -or [double]$value -lt 0); $attempt++){
                Start-Sleep -Milliseconds 500
                $excel.Calculate()
                $value=Read-CellValue $pv $address
            }
            if($null -eq $value -or $value -is [string] -or [double]$value -lt 0){
                [ordered]@{case=$case.case;year=$case.production_year;address=$address;value=$value;text=$pv.Range($address).Text;formula=$pv.Range($address).Formula;calculation_state=$excel.CalculationState} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRoot 'output\greet_case_failure.json') -Encoding UTF8
                throw "Invalid output $address : $value"
            }
            $record[$address]=[double]$value
        }
        # Capture direct inventory/combustion controls independently of GWP totals.
        $record['module_material_mass_control']=Read-CellValue $pv 'BV394'
        $record['wind_GHG_g_per_mmBtu']=Read-CellValue ($materials.Worksheets.Item('GREET1_Import_Export')) 'P361'
        $settled=$false
        for($round=0;$round -lt 10;$round++){
            $excel.Calculate()
            $changed=$false;$valid=$true
            foreach($address in @('BV476','CG476','CI476','CM476','D209','B254','D579','EE289','EC289','ED289','EG289','EF289','DR289','DX289')){
                $confirmed=Read-CellValue $pv $address
                if($null -eq $confirmed -or $confirmed -is [string] -or [double]$confirmed -lt 0){$valid=$false;continue}
                if([math]::Abs([double]$confirmed-[double]$record[$address]) -gt 1e-7*[math]::Max(1,[double]$record[$address])){$changed=$true}
                $record[$address]=[double]$confirmed
            }
            if($valid -and -not $changed){$settled=$true;break}
            Start-Sleep -Milliseconds 300
        }
        if(-not $settled){throw 'Outputs did not settle within ten follow-on calculations'}
        $results += $record
        $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $partialPath -Encoding UTF8
        Write-Output ('Completed '+$case.case+' '+$case.production_year+'; module kg CO2e/m2='+([double]$record['BV476']/1000))
    }
    $name=if($KeyYearsOnly){'greet_key_year_results.json'}else{$ResultName+'.json'}
    $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $taskRoot ('output\'+$name)) -Encoding UTF8
}finally{
    if($materials){$materials.Close($false)}
    if($energy){$energy.Close($false)}
    if($excel){$excel.Quit();[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)}
}
