"""
diagnose.py  —  Run this in your project folder to find the exact problem.
    python diagnose.py
"""
import sys, os
print("\n" + "="*55)
print("  WILDFIRE SYSTEM DIAGNOSTIC")
print("="*55)

# ── Test 1: Which predictor.py is loaded? ─────────────────
print("\n[1] PREDICTOR.PY CHECK")
import predictor
src = open(predictor.__file__).read()
if 'TN_SEASONAL_DMC0' in src:
    print("    ✅ NEW predictor.py loaded (has seasonal FWI fix)")
elif 'TN_THRESHOLDS' in src:
    print("    ⚠️  PARTIAL fix — has thresholds but NOT seasonal FWI")
else:
    print("    ❌ OLD predictor.py loaded — THIS IS THE PROBLEM!")
    print(f"    File: {predictor.__file__}")
    print("    → Replace this file with the new predictor.py from outputs!")

# ── Test 2: FWI calculation ────────────────────────────────
print("\n[2] FWI CALCULATION CHECK")
try:
    import math
    from datetime import datetime
    # Ooty safe conditions
    temp, rh, ws, rain = 22.4, 32, 5.83, 0
    # Quick FWI estimate
    mo = 147.2*(101-85)/(59.5+85)
    ed = 0.942*rh**0.679+11*math.exp((rh-100)/10)+0.18*(21.1-temp)*(1-math.exp(-0.115*rh))
    kd = 0.424*(1-(rh/100)**1.7)+0.0694*ws**0.5*(1-(rh/100)**8)
    m  = ed+(mo-ed)*10**(-kd*0.581*math.exp(0.0365*temp))
    ffmc = 59.5*(250-m)/(147.2+m)
    print(f"    FFMC from season-start defaults: {ffmc:.2f}")
    if ffmc > 85:
        print(f"    ✅ FFMC looks correct")
    
    # Check DMC starting value being used
    if 'TN_SEASONAL_DMC0' in src:
        month = datetime.now().month
        # Extract from predictor's dict
        import predictor as p
        dmc0 = p.TN_SEASONAL_DMC0[month]
        dc0  = p.TN_SEASONAL_DC0[month]
        print(f"    DMC0={dmc0}, DC0={dc0} for month {month}")
        if dmc0 >= 20:
            print(f"    ✅ Seasonal starting values correct")
        else:
            print(f"    ❌ DMC0 too low!")
    else:
        print("    ❌ Using fresh-start defaults (DMC0=6, DC0=15) — WRONG!")
        
except Exception as e:
    print(f"    Error: {e}")

# ── Test 3: Direct prediction test ────────────────────────
print("\n[3] DIRECT PREDICTION TEST")
print("    Testing Ooty (safe weather: 22°C, 32% RH, low wind)...")
try:
    result = predictor.predict_for_location(lat=11.4102, lon=76.695, name='Ooty Test')
    if result:
        prob = result['probability']*100
        risk = result['risk']['level']
        fwi_val = result['fwi']['FWI']
        dmc_val = result['fwi']['DMC']
        dc_val  = result['fwi']['DC']
        print(f"    Probability : {prob:.1f}%")
        print(f"    Risk Level  : {risk}")
        print(f"    DMC={dmc_val}, DC={dc_val}, FWI={fwi_val}")
        if prob > 80:
            print(f"    ❌ STILL WRONG! Probability too high for safe weather.")
            if dmc_val < 15:
                print(f"    → CAUSE: DMC={dmc_val} too low (old seasonal values)")
                print(f"    → ACTION: Replace predictor.py with latest version")
        elif prob < 55:
            print(f"    ✅ CORRECT! Ooty at {prob:.1f}% = {risk}")
        else:
            print(f"    ⚠️  Borderline — {prob:.1f}% shows as {risk}")
    else:
        print("    ❌ Prediction returned None — weather API failed?")
except Exception as e:
    print(f"    Error: {e}")

# ── Test 4: Config RISK_LEVELS ────────────────────────────
print("\n[4] CONFIG RISK_LEVELS CHECK")
import config
rl = config.RISK_LEVELS
high_start = rl.get('HIGH',(0,0))[0]*100
crit_start = rl.get('CRITICAL',(0,0))[0]*100
print(f"    HIGH starts at  : {high_start:.0f}%")
print(f"    CRITICAL starts at: {crit_start:.0f}%")
if high_start < 60:
    print(f"    ❌ HIGH threshold too low ({high_start:.0f}%) — normal TN weather triggers HIGH!")
    print(f"    → Edit config.py: set HIGH to (0.75, 0.88)")
else:
    print(f"    ✅ Thresholds look correct")

print("\n" + "="*55)
print("  DONE — Fix whatever showed ❌ above")
print("="*55 + "\n")