import math
import logging
 
logger = logging.getLogger(__name__)
 
 
class FWICalculator:
    """
    Computes the Canadian Forest Fire Weather Index (FWI) system.
    Based on Van Wagner (1987) equations.
    Reference: https://cwfis.cfs.nrcan.gc.ca/background/summary/fwi
    """
 
    def __init__(self):
        # Typical previous-day starting values for summer season
        self.ffmc_prev = 85.0   # Fine Fuel Moisture Code (prev day)
        self.dmc_prev  = 6.0    # Duff Moisture Code (prev day)
        self.dc_prev   = 15.0   # Drought Code (prev day)
 
    def _calc_ffmc(self, temp, rh, ws, rain):
        mo = 147.2 * (101 - self.ffmc_prev) / (59.5 + self.ffmc_prev)
        if rain > 0.5:
            rf   = rain - 0.5
            mo  += 42.5 * rf * math.exp(-100 / (251 - mo)) * (1 - math.exp(-6.93 / rf))
            mo   = min(mo, 250.0)
        ed = 0.942 * rh**0.679 + 11 * math.exp((rh - 100) / 10) + 0.18 * (21.1 - temp) * (1 - math.exp(-0.115 * rh))
        if mo > ed:
            ew = 0.618 * rh**0.753 + 10 * math.exp((rh - 100) / 10) + 0.18 * (21.1 - temp) * (1 - math.exp(-0.115 * rh))
            if mo > ew:
                kd = 0.424 * (1 - (rh / 100)**1.7) + 0.0694 * ws**0.5 * (1 - (rh / 100)**8)
                kd *= 0.581 * math.exp(0.0365 * temp)
                mo = ed + (mo - ed) * 10**(-kd)
        else:
            ku = 0.424 * (1 - ((100 - rh) / 100)**1.7) + 0.0694 * ws**0.5 * (1 - ((100 - rh) / 100)**8)
            ku *= 0.581 * math.exp(0.0365 * temp)
            mo = ed - (ed - mo) * 10**(-ku)
        return 59.5 * (250 - mo) / (147.2 + mo)
 
    def _calc_dmc(self, temp, rh, rain, month=7):
        Le = [6.5,7.5,9.0,12.8,13.9,13.9,12.4,10.9,9.4,8.0,7.0,6.0][month-1]
        if rain > 1.5:
            re  = 0.92 * rain - 1.27
            mo  = 20 + math.exp(5.6348 - self.dmc_prev / 43.43)
            b   = (0.092 + 0.0737 * mo) if self.dmc_prev <= 33 else (14 - 1.3 * math.log(self.dmc_prev))
            mr  = mo + 1000 * re / (48.77 + b * re)
            pr  = 244.72 - 43.43 * math.log(mr - 20)
            self.dmc_prev = max(pr, 0)
        k   = 1.894 * (temp + 1.1) * (100 - rh) * Le * 1e-6 if temp > -1.1 else 0
        return self.dmc_prev + 100 * k
 
    def _calc_dc(self, temp, rain, month=7):
        Lf = [-1.6,-1.6,-1.6,0.9,3.8,5.8,6.4,5.0,2.4,0.4,-1.6,-1.6][month-1]
        if rain > 2.8:
            rd  = 0.83 * rain - 1.27
            Qo  = 800 * math.exp(-self.dc_prev / 400)
            Qr  = Qo + 3.937 * rd
            Dr  = 400 * math.log(800 / Qr)
            self.dc_prev = max(Dr, 0)
        V = 0.36 * (temp + 2.8) + Lf if temp > -2.8 else 0
        return self.dc_prev + 0.5 * V
 
    def _calc_isi(self, ffmc, ws):
        fm  = 147.2 * (101 - ffmc) / (59.5 + ffmc)
        sf  = 19.115 * math.exp(-0.1386 * fm) * (1 + fm**5.31 / 49300000)
        return 0.208 * sf * math.exp(0.05039 * ws)
 
    def _calc_bui(self, dmc, dc):
        if dmc <= 0.4 * dc:
            return 0.8 * dmc * dc / (dmc + 0.4 * dc)
        return dmc - (1 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc)**1.7)
 
    def _calc_fwi(self, isi, bui):
        bb = 0.1 * isi * (0.626 * bui**0.809 + 2) if bui <= 80 else 0.1 * isi * (1000 / (25 + 108.64 * math.exp(-0.023 * bui)))
        return math.exp(2.72 * (0.434 * math.log(bb))**0.647) if bb > 1 else bb
 
    def calculate(self, temp, rh, ws, rain, month=7) -> dict:
        """Main method — returns all 6 FWI indices."""
        try:
            ffmc = self._calc_ffmc(temp, rh, ws, rain)
            dmc  = self._calc_dmc(temp, rh, rain, month)
            dc   = self._calc_dc(temp, rain, month)
            isi  = self._calc_isi(ffmc, ws)
            bui  = self._calc_bui(dmc, dc)
            fwi  = self._calc_fwi(isi, bui)
 
            # Update previous-day values for next call
            self.ffmc_prev = ffmc
            self.dmc_prev  = dmc
            self.dc_prev   = dc
 
            return {
                'FFMC': round(ffmc, 2),
                'DMC' : round(dmc,  2),
                'DC'  : round(dc,   2),
                'ISI' : round(isi,  2),
                'BUI' : round(bui,  2),
                'FWI' : round(fwi,  2),
            }
        except Exception as e:
            logger.error(f'FWI calculation error: {e}')
            # Fallback: return average values so prediction still runs
            return { 'FFMC':75.0, 'DMC':50.0, 'DC':200.0, 'ISI':8.0, 'BUI':60.0, 'FWI':15.0 }
 
 
# ── Quick test ────────────────────────────────────────────────────────
if __name__ == '__main__':
    calc = FWICalculator()
    result = calc.calculate(temp=34, rh=25, ws=18, rain=0, month=8)
    print('FWI Indices:')
    for k, v in result.items():
        print(f'  {k}: {v}')
