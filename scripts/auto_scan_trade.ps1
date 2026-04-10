# OKX Auto Scan & Trade Script
# API 密钥从环境变量读取，或通过 okx config init 配置
if (-not $env:OKX_API_KEY -or -not $env:OKX_SECRET_KEY -or -not $env:OKX_PASSPHRASE) {
    Write-Host "ERROR: 请设置环境变量 OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE"
    Write-Host "  或运行 okx config init 后重新加载环境变量"
    exit 1
}

$RSI_PERIOD = 14
$RSI_THRESHOLD = 25
$TP_PCT = 8.0
$SL_PCT = 5.0
$LEVERAGE = 5
$POSITION_PCT = 40

Write-Host "============================================================"
Write-Host "OKX Agent Trade Kit - Market Scan"
Write-Host "============================================================"

# Phase 0: Check positions
Write-Host ""
Write-Host "[Phase 0] Checking positions..."
$positions_out = okx swap positions 2>&1 | Out-String
if ($positions_out -notmatch "No open positions" -and $positions_out.Trim() -ne "") {
    Write-Host "  Found open positions, skip this scan"
    Write-Host $positions_out
    exit 0
}
Write-Host "  No open positions"

# Get balance
Write-Host ""
Write-Host "[Phase 0] Getting balance..."
$balance_out = okx account balance 2>&1 | Out-String
Write-Host "Balance output:"
Write-Host $balance_out

# Parse available USDT
$lines = $balance_out -split "`n"
$available = 0.0
foreach ($line in $lines) {
    if ($line -match "USDT" -and $line -match "([0-9]+\.[0-9]+)") {
        $available = [double]$matches[1]
        break
    }
}
if ($available -le 0) {
    Write-Host "  Cannot parse balance, output:"
    Write-Host $balance_out
    exit 1
}
Write-Host "  Available USDT: $available"

# Phase 1: Scan market
Write-Host ""
Write-Host "[Phase 1] Scanning market RSI..."

$symbols = @(
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
    "BNB-USDT-SWAP",
    "DOGE-USDT-SWAP",
    "XRP-USDT-SWAP",
    "ADA-USDT-SWAP",
    "AVAX-USDT-SWAP",
    "DOT-USDT-SWAP",
    "LINK-USDT-SWAP"
)

# ctVal lookup (合约面值 = 每张合约对应基础货币数量)
$ctValMap = @{}
$ctValMap["BTC"] = 0.01
$ctValMap["ETH"] = 0.1
$ctValMap["SOL"] = 1
$ctValMap["BNB"] = 0.01
$ctValMap["DOGE"] = 1000
$ctValMap["XRP"] = 100
$ctValMap["ADA"] = 100
$ctValMap["AVAX"] = 1
$ctValMap["DOT"] = 1
$ctValMap["LINK"] = 1

$results = @()
foreach ($sym in $symbols) {
    Write-Host "  Scanning $sym..."
    $ticker_out = okx market ticker $sym 2>&1 | Out-String
    $last = 0.0; $change = 0.0
    foreach ($tline in $ticker_out -split "`n") {
        if ($tline -match "last\s+([0-9]+\.?[0-9]*)") { $last = [double]$matches[1] }
        if ($tline -match "24h change %\s+([-0-9]+\.?[0-9]*)") { $change = [double]$matches[1] }
    }
    if ($last -eq 0) { continue }

    # Get 1H candles
    $candle_out = okx market candles $sym --bar 1H --limit 100 2>&1 | Out-String
    $candle_lines = @()
    foreach ($c in ($candle_out -split "`n")) {
        $c = $c.Trim()
        if ($c -ne "" -and $c -notmatch "^last" -and $c -notmatch "^open" -and $c -notmatch "^time" -and $c -notmatch "error" -and $c -notmatch "Error") {
            $candle_lines += $c
        }
    }

    $closes = @()
    foreach ($cl in $candle_lines) {
        $parts = $cl -split "\s+" | Where-Object { $_ -ne "" }
        if ($parts.Count -ge 6) {
            $closeStr = $parts[4]
            try { $closes += [double]$closeStr } catch {}
        }
    }

    if ($closes.Count -lt $RSI_PERIOD + 1) { continue }

    # Calc RSI
    $gains = @(); $losses = @()
    for ($i = 1; $i -lt $closes.Count; $i++) {
        $delta = $closes[$i] - $closes[$i-1]
        $gains += if ($delta -gt 0) { $delta } else { 0 }
        $losses += if ($delta -lt 0) { -$delta } else { 0 }
    }
    $recentGains = $gains | Select-Object -Last $RSI_PERIOD
    $recentLosses = $losses | Select-Object -Last $RSI_PERIOD
    $avgGain = ($recentGains | Measure-Object -Sum).Sum / $RSI_PERIOD
    $avgLoss = ($recentLosses | Measure-Object -Sum).Sum / $RSI_PERIOD
    if ($avgLoss -eq 0) { $rsi = 100.0 } else { $rsi = 100.0 - (100.0 / (1.0 + $avgGain / $avgLoss)) }

    $symShort = $sym -replace "-USDT-SWAP", ""
    $results += [PSCustomObject]@{
        Symbol = $sym
        Name = $symShort
        RSI = [Math]::Round($rsi, 1)
        Price = $last
        Change24h = $change
    }
    Write-Host "    RSI=$([Math]::Round($rsi,1)) Price=$last Change=$($change.ToString('F2'))%"
}

if ($results.Count -eq 0) {
    Write-Host "  No valid market data found"
    exit 1
}

$results = $results | Sort-Object RSI

Write-Host ""
Write-Host "============================================================"
Write-Host "RSI Scan Results (sorted by oversold)"
Write-Host "============================================================"
Write-Host ("{0,-8} {1,-10} {2,8} {3,14} {4,10}" -f "Status", "Symbol", "RSI", "Price", "24h Chg")
Write-Host ("-" * 55)
foreach ($r in $results) {
    $flag = if ($r.RSI -lt $RSI_THRESHOLD) { "RED" } elseif ($r.RSI -lt 40) { "YEL" } else { "GRN" }
    Write-Host ("{0,-8} {1,-10} {2,8:F1} {3,14:F4} {4,9:F2}%" -f $flag, $r.Name, $r.RSI, $r.Price, $r.Change24h)
}

# Phase 2: Open position if oversold found
$oversold = $results | Where-Object { $_.RSI -lt $RSI_THRESHOLD }
if ($oversold.Count -eq 0) {
    Write-Host ""
    Write-Host "No oversold signal found (RSI<$RSI_THRESHOLD). Stay empty."
    exit 0
}

$best = $oversold[0]
$instId = $best.Symbol
$entryPrice = $best.Price

Write-Host ""
Write-Host "[Phase 2] Signal triggered!"
Write-Host "  Symbol: $instId"
Write-Host "  RSI: $($best.RSI)"
Write-Host "  Price: $entryPrice"

# Calc position size - isolated mode
# margin = position_value / leverage, position_value = contracts * price * ctVal
# => contracts = (available * position_pct * leverage) / (price * ctVal)
$maxMargin = $available * $POSITION_PCT / 100
$maxNotional = $maxMargin * $LEVERAGE

# Find ctVal from symbol
$symBase = $instId -replace "-USDT-SWAP", ""
$ctVal = $ctValMap[$symBase]
if (-not $ctVal) { $ctVal = 0.01 }

$contractQty = [Math]::Floor($maxMargin * $LEVERAGE / $entryPrice / $ctVal)
if ($contractQty -lt 1) { $contractQty = 1 }

$positionActualValue = $contractQty * $entryPrice * $ctVal
$marginUsed = $positionActualValue / $LEVERAGE

$tpPrice = [Math]::Round($entryPrice * (1 + $TP_PCT / 100), 4)
$slPrice = [Math]::Round($entryPrice * (1 - $SL_PCT / 100), 4)
$liqPrice = [Math]::Round($entryPrice * (1 - 1 / $LEVERAGE), 4)
$safetyMargin = ($entryPrice - $liqPrice) / $entryPrice * 100

Write-Host ""
Write-Host "Calc debug:"
Write-Host ("  Available: " + "$($available.ToString('F2'))" + ", Position: ${POSITION_PCT}% = " + "$($maxMargin.ToString('F2'))")
Write-Host ("  Symbol base: $symBase, Price: " + "$($entryPrice.ToString('F4'))" + ", Leverage: ${LEVERAGE}x, ctVal: $ctVal")
Write-Host ("  Max notional: " + "$($maxNotional.ToString('F2'))" + ", Contracts: $contractQty")
$positionActualValue2 = $contractQty * $entryPrice * $ctVal
$marginUsed2 = $positionActualValue2 / $LEVERAGE
Write-Host ("  Actual position: " + "$($positionActualValue2.ToString('F2'))" + ", Margin used: " + "$($marginUsed2.ToString('F2'))")

Write-Host ""
Write-Host "Position plan:"
Write-Host ("  Size: ${POSITION_PCT}% of " + "$($available.ToString('F2'))" + " = " + "$($maxMargin.ToString('F2'))")
Write-Host ("  Leverage: ${LEVERAGE}x")
Write-Host ("  Contracts: $contractQty (position: " + "$($positionActualValue2.ToString('F2'))" + " USDT, margin: " + "$($marginUsed2.ToString('F2'))" + " USDT)")
Write-Host ("  TP: " + "$($tpPrice.ToString('F4'))" + " (+${TP_PCT}%)")
Write-Host ("  SL: " + "$($slPrice.ToString('F4'))" + " (-${SL_PCT}%)")
Write-Host ("  Liq: " + "$($liqPrice.ToString('F4'))" + " (safety: " + "$($safetyMargin.ToString('F1'))" + "%)")

if ($safetyMargin -lt 5) {
    Write-Host "  REJECTED: Safety margin < 5%"
    exit 0
}

# Set leverage
Write-Host ""
Write-Host "Setting leverage ${LEVERAGE}x..."
$lev_out = okx swap leverage --instId $instId --lever $LEVERAGE --mgnMode isolated --posSide long 2>&1 | Out-String
Write-Host $lev_out

# Open position
Write-Host ""
Write-Host "Opening long position..."
$order_out = okx swap place --instId $instId --side buy --tdMode isolated --posSide long --ordType market --sz $contractQty 2>&1 | Out-String
Write-Host $order_out

if ($order_out -match "Order placed" -or ($order_out -match "OK" -and $order_out -notmatch "Error")) {
    Write-Host "Position opened!"

    # Get actual entry price
    Start-Sleep -Seconds 2
    $pos_out = okx swap positions --instId $instId 2>&1 | Out-String
    Write-Host "Position check:"
    Write-Host $pos_out
    foreach ($pl in ($pos_out -split "`n")) {
        if ($pl -match "avgPx\s+([0-9]+\.?[0-9]*)") {
            $actualEntry = [double]$matches[1]
            Write-Host ("Actual entry: " + "$($actualEntry.ToString('F4'))")
            $tpPrice = [Math]::Round($actualEntry * (1 + $TP_PCT / 100), 4)
            $slPrice = [Math]::Round($actualEntry * (1 - $SL_PCT / 100), 4)
            break
        }
    }

    # Set TP/SL as OCO order
    Write-Host ""
    Write-Host ("Setting TP=" + "$($tpPrice.ToString('F4'))" + " SL=" + "$($slPrice.ToString('F4'))" + " (OCO)...")
    $algo_out = okx swap algo place --instId $instId --side sell --sz $contractQty --ordType oco --tpTriggerPx $tpPrice --tpOrdPx $tpPrice --slTriggerPx $slPrice --slOrdPx $slPrice --posSide long --tdMode isolated 2>&1 | Out-String
    Write-Host $algo_out

    if ($algo_out -match "Order placed" -or $algo_out -match "OK") {
        Write-Host "TP/SL set successfully!"
    } else {
        Write-Host "TP/SL setup may have failed. Manual check needed."
    }
} else {
    Write-Host "Position open failed!"
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Scan complete - $(Get-Date -Format 'yyyy/MM/dd HH:mm:ss')"
Write-Host "============================================================"
