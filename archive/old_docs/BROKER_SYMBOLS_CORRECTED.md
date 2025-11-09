# ✅ BROKER SYMBOLS CORRECTED - ACTUAL BROKER FORMAT

**Date**: November 20, 2025, 5:42 PM  
**Issue**: Contract codes come BEFORE .sim suffix (not after)  
**Fix**: Updated symbol cleaning logic

---

## ACTUAL BROKER FORMAT (from screenshot):

```
XAUZ25.sim       ← Gold December 2025
XAUG26.sim       ← Gold February 2026
USOILF26.sim     ← Oil January 2026
US500Z25.sim     ← S&P 500 December 2025
US100Z25.sim     ← Nasdaq December 2025
US30Z25.sim      ← Dow Jones December 2025
BTCX25.sim       ← Bitcoin November 2025
EURNOK.sim       ← EUR/NOK
USDZAR.sim       ← USD/ZAR
USDNOK.sim       ← USD/NOK
```

**Format**: `[SYMBOL][CONTRACT].sim`  
**NOT**: `[SYMBOL].sim[CONTRACT]`

---

## CORRECTED CLEANING LOGIC:

```python
# Step 1: Remove .sim suffix
symbol = raw_symbol.replace('.sim', '').replace('.SIM', '')

# Step 2: Remove contract codes (Z25, F26, G26, etc.)
# All contract months: Z F G H J K M N Q U V X
symbol = re.sub(r'[ZFGHJKMNQUVX]\d{2}$', '', symbol, flags=re.IGNORECASE)

# Step 3: Convert to lowercase
symbol = symbol.lower()
```

---

## CONTRACT CODE REFERENCE:

| Code | Month | Example |
|------|-------|---------|
| Z | December | XAUZ25.sim → xau |
| F | January | USOILF26.sim → usoil |
| G | February | XAUG26.sim → xau |
| H | March | US30H26.sim → us30 |
| J | April | US30J26.sim → us30 |
| K | May | US30K26.sim → us30 |
| M | June | US30M26.sim → us30 |
| N | July | US30N26.sim → us30 |
| Q | August | US30Q26.sim → us30 |
| U | September | US30U26.sim → us30 |
| V | October | US30V26.sim → us30 |
| X | November | BTCX25.sim → btc |

---

## SYMBOL MAPPING (CORRECTED):

### Supported Symbols:

| Broker Symbol | Cleaned | Model File | Status |
|--------------|---------|------------|--------|
| XAUZ25.sim | xau | xau_ensemble_latest.pkl | ✅ |
| XAUG26.sim | xau | xau_ensemble_latest.pkl | ✅ |
| USOILF26.sim | usoil | usoil_ensemble_latest.pkl | ✅ |
| US30Z25.sim | us30 | us30_ensemble_latest.pkl | ✅ |
| US100Z25.sim | us100 | us100_ensemble_latest.pkl | ✅ |
| US500Z25.sim | us500 | us500_ensemble_latest.pkl | ✅ |
| EURUSD.sim | eurusd | eurusd_ensemble_latest.pkl | ✅ |
| GBPUSD.sim | gbpusd | gbpusd_ensemble_latest.pkl | ✅ |
| USDJPY.sim | usdjpy | usdjpy_ensemble_latest.pkl | ✅ |

### Unsupported (no models):

| Broker Symbol | Cleaned | Status |
|--------------|---------|--------|
| BTCX25.sim | btc | ⚠️ No model |
| EURNOK.sim | eurnok | ⚠️ No model |
| USDZAR.sim | usdzar | ⚠️ No model |
| USDNOK.sim | usdnok | ⚠️ No model |

---

## EXAMPLES:

```
XAUZ25.sim      → xau       ✅ (Gold model)
XAUG26.sim      → xau       ✅ (Gold model)
USOILF26.sim    → usoil     ✅ (Oil model)
US500Z25.sim    → us500     ✅ (Indices model)
US100Z25.sim    → us100     ✅ (Indices model)
US30Z25.sim     → us30      ✅ (Indices model)
EURUSD.sim      → eurusd    ✅ (Forex model)
GBPUSD.sim      → gbpusd    ✅ (Forex model)
USDJPY.sim      → usdjpy    ✅ (Forex model)
BTCX25.sim      → btc       ⚠️ (No model - will return HOLD)
EURNOK.sim      → eurnok    ⚠️ (No model - will return HOLD)
```

---

## WHAT WAS WRONG:

**Before** (incorrect):
```python
symbol = raw_symbol.replace('.sim', '')  # XAUZ25 → XAUZ25
symbol = re.sub(r'[ZFG]\d+', '', symbol)  # XAUZ25 → XAU ✅
```

**Issue**: Only handled Z, F, G (not all 12 contract months)

**After** (correct):
```python
symbol = raw_symbol.replace('.sim', '')  # XAUZ25.sim → XAUZ25
symbol = re.sub(r'[ZFGHJKMNQUVX]\d{2}$', '', symbol)  # XAUZ25 → XAU ✅
```

**Fix**: Handles all 12 contract months (Z F G H J K M N Q U V X)

---

## VERIFICATION:

### Test Results:
```
XAUZ25.sim       → xau      ✅
XAUG26.sim       → xau      ✅
USOILF26.sim     → usoil    ✅
US500Z25.sim     → us500    ✅
US100Z25.sim     → us100    ✅
US30Z25.sim      → us30     ✅
BTCX25.sim       → btc      ⚠️ (no model)
EURNOK.sim       → eurnok   ⚠️ (no model)
USDZAR.sim       → usdzar   ⚠️ (no model)
USDNOK.sim       → usdnok   ⚠️ (no model)
```

---

## STATUS:

**Symbol Cleaning**: ✅ Fixed  
**Contract Codes**: ✅ All 12 months supported  
**Broker Format**: ✅ Matches screenshot  
**API Updated**: ✅ Restarted  
**Models**: ✅ 11 loaded, 0 errors  

**BROKER SYMBOLS NOW MATCH ACTUAL BROKER FORMAT!** 🎯
