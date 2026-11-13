"""Re-runs the checks from 'PV NPC Progress poushra.pdf' with the Python model."""
import time, numpy as np
from pvnpc import run, COLS
c = {n: k for k, n in enumerate(COLS)}

def stats(L, Tstop=1.2):
    w = L[:, 0] > Tstop - 0.1
    P = np.mean(L[w, c['Vpv']] * L[w, c['Ipv']]) / 1e3
    pk = lambda a: np.mean(np.sqrt(2 * np.mean(L[w][:, [c[a + '_a'], c[a + '_b'], c[a + '_c']]]**2, axis=0)))
    return dict(P=P, Vpv=L[w, c['Vpv']].mean(), Iabc=pk('Iabc'), Iinv=pk('Iinv'), Vdc=L[w, c['Vdc']].mean(),
                ia=L[w, c['Iinv_a']], vab=L[w, c['Vab']])

rows = []
def chk(name, got, want, tol):
    ok = abs(got - want) <= tol
    rows.append((name, got, want, 'PASS' if ok else 'FAIL'))
    print(f'{name:32s} {got:10.3f}  note {want:9.3f}  {"PASS" if ok else "FAIL"}', flush=True)

t0 = time.time(); run(Tstop=0.01)  # compile
print(f'compiled in {time.time()-t0:.1f}s'); t0 = time.time()
h = stats(run())
chk('Healthy PV power (kW)', h['P'], 100.4, 2.0)
chk('Grid-side current peak (A)', h['Iabc'], 3.29, 0.15)
chk('Inverter current peak (A)', h['Iinv'], 318, 15)
chk('Iinv/Iabc ratio', h['Iinv'] / h['Iabc'], 96.4, 2.5)
chk('Mean Vdc (V)', h['Vdc'], 500, 10)
chk('PV power 200 W/m2 (kW)', stats(run(G=200))['P'], 19.3, 1.5)
r = stats(run(boost_on=0)); chk('C13 PV power (kW)', r['P'], 0, 2); chk('C13 PV voltage (V)', r['Vpv'], 320.8, 8)
chk('C14 shading nB=26 30% (kW)', stats(run(nB=26, shade_prof=[[0, 1], [.8, 1], [.9, .3], [10, .3]]))['P'], 72.4, 2)
chk('C15 string open nB=10 (kW)', stats(run(nB=10, shade_prof=[[0, 1], [.8, 1], [.801, 0], [10, 0]]))['P'], 84.8, 2)
chk('C15 string open nB=20 (kW)', stats(run(nB=20, shade_prof=[[0, 1], [.8, 1], [.801, 0], [10, 0]]))['P'], 69.7, 2)
chk('Cloud dip 1000->300 (kW)', stats(run(Gprof=[[0, 1000], [.8, 1000], [.9, 300], [10, 300]]))['P'], 30, 2)
chk('C17 sag 30% current ratio', stats(run(sag_step=-0.3))['Iabc'] / h['Iabc'], 1.423, 0.1)
m1 = np.ones(12); m1[0] = 0; m2 = np.ones(12); m2[1] = 0
a, b = stats(run(gate_mask=m1)), stats(run(gate_mask=m2))
print(f"{'S1 vs S2 ia difference':32s} {np.sqrt(np.mean((a['ia']-b['ia'])**2))/np.sqrt(np.mean(a['ia']**2))*100:9.2f} %  note 1.3 %")
print(f"{'S1 vs S2 Vab difference':32s} {np.sqrt(np.mean((a['vab']-b['vab'])**2))/np.sqrt(np.mean(a['vab']**2))*100:9.2f} %  note 5.6 %")
print(f'\n{sum(r[3]=="PASS" for r in rows)}/{len(rows)} PASS, 13 simulations in {time.time()-t0:.1f}s')
