import re
src = open('ea/AgenticTrade.mq5').read()
for a, b in [('{', '}'), ('(', ')'), ('[', ']')]:
    print(a + b, src.count(a), src.count(b))
print('magic literal count:', src.count('20261104'))
for fn in ['SymbolAllowed', 'ProcessSignal', 'CalcLotByRisk', 'CountOwnPositions',
           'CloseAllPositions', 'LogGuard', 'CheckKillSwitch', 'CheckDailyLoss',
           'InNewsWindow', 'InKillzone', 'OnInit', 'OnTick', 'UpdateDailyRollover',
           'UpdateEquityHwm']:
    print(fn, 'defined' if re.search(r'\b' + fn + r'\s*\(', src) else 'MISSING')
print('lines:', src.count('\n'))
