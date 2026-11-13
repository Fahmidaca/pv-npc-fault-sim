"""Exact maximum power of the PV array (SunPower SPR-305E parameters from pv_npc_fault.slx, 330 modules, 25 degC)."""
import numpy as np
from scipy.optimize import brentq
NCELL, IL0, I0, NI, RSH, RS = 96, 6.0092, 6.3014e-12, 0.94504, 269.5934, 0.37152
vt = NI * NCELL * 1.380649e-23 * 298.15 / 1.602177e-19
I = lambda V, G: brentq(lambda i: IL0 * G / 1000 - I0 * (np.exp((V + i * RS) / vt) - 1) - (V + i * RS) / RSH - i, -20, 20)
for G in (1000, 800, 600, 400, 300, 200):
    v = np.linspace(30, 64, 3000); p = np.array([x * I(x, G) for x in v]); k = p.argmax()
    print(f'{G:5d} W/m2: array Pmax {p[k]*330/1e3:6.1f} kW at {v[k]*5:5.1f} V')
