# CodeBridge - vigia do app desktop do Claude.
# Observa, via UI Automation do Windows, o botao "Interromper resposta"
# (ou "Stop response") do app Claude e escreve uma linha no stdout a cada
# mudanca de estado: RUNNING, IDLE ou NO_APP. Nao le o texto da conversa.
param(
    [int]$ParentPid = 0,
    [int]$IntervalMs = 300,
    # Polls seguidos sem o botao antes de reportar IDLE (10 x 300 ms = 3 s):
    # trocar de conversa tira o botao da tela por ~1-2 s.
    [int]$IdleConfirm = 10
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes

$A = [System.Windows.Automation.AutomationElement]
$Scope = [System.Windows.Automation.TreeScope]
$names = @('Interromper resposta', 'Stop response')

$nameConds = [System.Windows.Automation.Condition[]]@(
    $names | ForEach-Object {
        [System.Windows.Automation.PropertyCondition]::new($A::NameProperty, $_)
    }
)
$buttonCond = [System.Windows.Automation.PropertyCondition]::new(
    $A::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Button
)
$cond = [System.Windows.Automation.AndCondition]::new(
    [System.Windows.Automation.Condition[]]@(
        $buttonCond,
        [System.Windows.Automation.OrCondition]::new($nameConds)
    )
)

$reported = ''
$idleStreak = 0

while ($true) {
    if ($ParentPid -gt 0) {
        if (-not (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue)) {
            break
        }
    }

    $observed = $null
    try {
        $pids = @(
            Get-Process -Name 'Claude' -ErrorAction SilentlyContinue |
                ForEach-Object { $_.Id }
        )
        if ($pids.Count -eq 0) {
            $observed = 'NO_APP'
        }
        else {
            $observed = 'IDLE'
            $windows = $A::RootElement.FindAll(
                $Scope::Children,
                [System.Windows.Automation.Condition]::TrueCondition
            )
            foreach ($window in $windows) {
                if ($pids -contains $window.Current.ProcessId) {
                    if ($null -ne $window.FindFirst($Scope::Descendants, $cond)) {
                        $observed = 'RUNNING'
                        break
                    }
                }
            }
        }
    }
    catch {
        # Arvore de acessibilidade em reconstrucao: mantem o ultimo estado.
        $observed = $null
    }

    $next = $reported
    if ($observed -eq 'RUNNING') {
        $idleStreak = 0
        $next = 'RUNNING'
    }
    elseif ($null -ne $observed) {
        $idleStreak++
        if ($reported -ne 'RUNNING' -or $idleStreak -ge $IdleConfirm) {
            $next = $observed
        }
    }

    if ($next -and $next -ne $reported) {
        [Console]::Out.WriteLine($next)
        [Console]::Out.Flush()
        $reported = $next
    }

    Start-Sleep -Milliseconds $IntervalMs
}
