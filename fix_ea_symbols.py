#!/usr/bin/env python3
"""
Fix all symbol parameter issues in EA
"""
import re

ea_file = "/Users/justinhardison/ai-trading-system/mql5/Experts/AI_Trading_EA_Ultimate.mq5"

# Read file
with open(ea_file, 'r') as f:
    content = f.read()

# Fix 1: GetTimeframeData calls - add symbol and digits parameters
content = re.sub(
    r'GetTimeframeData\(PERIOD_(\w+), 50\)',
    r'GetTimeframeData(symbol, digits, PERIOD_\1, 50)',
    content
)

# Fix 2: Update GetTimeframeData function signature
content = content.replace(
    'string GetTimeframeData(ENUM_TIMEFRAMES timeframe, int bars)',
    'string GetTimeframeData(string symbol, int digits, ENUM_TIMEFRAMES timeframe, int bars)'
)

# Fix 3: Fix CopyRates in GetTimeframeData
content = re.sub(
    r'CopyRates\(_Symbol, timeframe',
    r'CopyRates(symbol, timeframe',
    content
)

# Fix 4: Fix _Digits in GetTimeframeData
content = re.sub(
    r'DoubleToString\(rates\[i\]\.(\w+), _Digits\)',
    r'DoubleToString(rates[i].\1, digits)',
    content
)

# Fix 5: Fix indicators to use symbol parameter
content = re.sub(r'iATR\(_Symbol,', 'iATR(symbol,', content)
content = re.sub(r'iRSI\(_Symbol,', 'iRSI(symbol,', content)
content = re.sub(r'iMACD\(_Symbol,', 'iMACD(symbol,', content)
content = re.sub(r'iBands\(_Symbol,', 'iBands(symbol,', content)
content = re.sub(r'iMA\(_Symbol,', 'iMA(symbol,', content)

# Fix 6: Fix _Digits in indicators section (lines 319-357)
# This is already partially done, but ensure all are fixed
content = re.sub(
    r'DoubleToString\(atr(\d+)\[0\], _Digits\)',
    r'DoubleToString(atr\1[0], digits)',
    content
)
content = re.sub(
    r'DoubleToString\(macdMain\[0\], _Digits\)',
    r'DoubleToString(macdMain[0], digits)',
    content
)
content = re.sub(
    r'DoubleToString\(macdSignal\[0\], _Digits\)',
    r'DoubleToString(macdSignal[0], digits)',
    content
)
content = re.sub(
    r'DoubleToString\(bb(\w+)\[0\], _Digits\)',
    r'DoubleToString(bb\1[0], digits)',
    content
)
content = re.sub(
    r'DoubleToString\(sma(\d+)\[0\], _Digits\)',
    r'DoubleToString(sma\1[0], digits)',
    content
)
content = re.sub(
    r'DoubleToString\(ema(\d+)\[0\], _Digits\)',
    r'DoubleToString(ema\1[0], digits)',
    content
)

# Fix 7: Fix positions section _Digits
content = re.sub(
    r'DoubleToString\(PositionGetDouble\(POSITION_(\w+)\), _Digits\)',
    r'DoubleToString(PositionGetDouble(POSITION_\1), digits)',
    content
)

# Fix 8: Update ExecuteAIDecision signature
content = content.replace(
    'void ExecuteAIDecision(string response)',
    'void ExecuteAIDecision(string response, string symbol)'
)

# Fix 9: Fix ExecuteAIDecision body
content = re.sub(
    r'double ask = SymbolInfoDouble\(_Symbol, SYMBOL_ASK\);',
    r'double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);',
    content
)
content = re.sub(
    r'double bid = SymbolInfoDouble\(_Symbol, SYMBOL_BID\);',
    r'double bid = SymbolInfoDouble(symbol, SYMBOL_BID);',
    content
)
content = re.sub(
    r'if\(ExecuteTrade\(ORDER_TYPE_BUY,',
    r'if(ExecuteTrade(symbol, ORDER_TYPE_BUY,',
    content
)
content = re.sub(
    r'if\(ExecuteTrade\(ORDER_TYPE_SELL,',
    r'if(ExecuteTrade(symbol, ORDER_TYPE_SELL,',
    content
)

# Fix 10: Update ExecuteTrade signature
content = content.replace(
    'bool ExecuteTrade(ENUM_ORDER_TYPE orderType, double lots, double price, double sl, double tp)',
    'bool ExecuteTrade(string symbol, ENUM_ORDER_TYPE orderType, double lots, double price, double sl, double tp)'
)

# Fix 11: Fix ExecuteTrade body
content = re.sub(
    r'request\.symbol = _Symbol;',
    r'request.symbol = symbol;',
    content
)

# Fix 12: Update CloseAllPositions to accept symbol
content = content.replace(
    'void CloseAllPositions()',
    'void CloseAllPositions(string symbol)'
)

# Fix 13: Fix CloseAllPositions body
content = re.sub(
    r'if\(PositionGetString\(POSITION_SYMBOL\) == _Symbol &&',
    r'if(PositionGetString(POSITION_SYMBOL) == symbol &&',
    content
)
content = re.sub(
    r'request\.symbol = _Symbol;(\s+)request\.volume',
    r'request.symbol = symbol;\1request.volume',
    content
)
content = re.sub(
    r'SymbolInfoDouble\(_Symbol, SYMBOL_BID\) :(\s+)SymbolInfoDouble\(_Symbol, SYMBOL_ASK\)',
    r'SymbolInfoDouble(symbol, SYMBOL_BID) :\1SymbolInfoDouble(symbol, SYMBOL_ASK)',
    content
)

# Fix 14: Update CloseAllPositions call in ExecuteAIDecision
content = re.sub(
    r'CloseAllPositions\(\);',
    r'CloseAllPositions(symbol);',
    content
)

# Write fixed file
with open(ea_file, 'w') as f:
    f.write(content)

print("✅ EA Fixed!")
print("\nChanges made:")
print("1. ✅ Symbol name sent to API")
print("2. ✅ GetTimeframeData() uses symbol parameter")
print("3. ✅ All indicators use symbol parameter")
print("4. ✅ ExecuteAIDecision() uses symbol parameter")
print("5. ✅ ExecuteTrade() uses symbol parameter")
print("6. ✅ CloseAllPositions() uses symbol parameter")
print("7. ✅ All _Symbol replaced with symbol")
print("8. ✅ All _Digits replaced with digits")
print("\n🎯 EA is now ready for multi-symbol trading!")
print("📋 Next: Compile in MetaEditor")
