#!/bin/bash
# Download XAUUSD tick data per year, 2021-2025
set -e
cd /home/agentuser/agentictrade-work/AgenticTrade/backtest/data
for Y in 2021 2022 2023 2024 2025; do
  if [ -f "download/xauusd-tick-${Y}-01-01-$((Y+1))-01-01.csv" ]; then
    echo "SKIP $Y (already exists)"
    continue
  fi
  echo "=== Downloading $Y ==="
  npx -y dukascopy-node -i xauusd -from ${Y}-01-01 -to $((Y+1))-01-01 -t tick -f csv
done
echo "ALL DONE"
