"""Generates the 360-run fault dataset (18 classes x 20 weather profiles), crash-safe and reproducible.
Usage: python make_dataset.py [--sample | --pilot] [--workers N]"""
import os, sys, csv, time, numpy as np
from multiprocessing import Pool
from pvnpc import run, COLS

OUT = os.path.join('dataset', 'runs')
GROUP = [0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 8, 9, 10, 11]
GNAME = ['Healthy', 'NPC_a_upper', 'NPC_a_lower', 'NPC_b_upper', 'NPC_b_lower', 'NPC_c_upper', 'NPC_c_lower',
         'Boost_open', 'Partial_shading', 'String_open', 'Sensor_gain', 'Grid_sag']

def weather(p, Tf):
    if p < 15:
        G, T = [200, 400, 600, 800, 1000][p // 3], [15, 30, 45][p % 3]
        return [[0, G], [10, G]], T
    t = np.linspace(0, 2, 2001)
    g = {15: np.interp(t, [0, Tf - .1, Tf + .1, 2], [1000, 1000, 400, 400]),
         16: np.interp(t, [0, Tf - .1, Tf + .1, 2], [400, 400, 1000, 1000]),
         17: np.interp(t, [0, Tf - .1, Tf, Tf + .1, Tf + .2, 2], [900, 900, 300, 300, 900, 900]),
         18: np.interp(t, [0, Tf, Tf + .02, 2], [700, 700, 250, 250]),
         19: 600 + 150 * np.sin(2 * np.pi * 3 * t)}[p]
    return np.c_[t, g].tolist(), 30

def plan():
    rows = []
    for cls in range(18):
        for p in range(20):
            n = len(rows) + 1; rng = np.random.default_rng(1000 + n)
            Tf = 0.8 + rng.uniform(0, 1 / 60)
            Gp, T = weather(p, Tf)
            kw = dict(Gprof=Gp, T=T, Tf=Tf, Tstop=Tf + 0.4, seed=1000 + n); par = ''
            if 1 <= cls <= 12:
                m = np.ones(12); m[cls - 1] = 0; kw['gate_mask'] = m; par = f'switch={cls}'
            elif cls == 13: kw['boost_on'] = 0
            elif cls in (14, 15):
                nB = int(rng.integers(13, 41)) if cls == 14 else int(rng.integers(4, 21))
                k = rng.uniform(.2, .6) if cls == 14 else 0.0
                ramp = rng.uniform(.05, .2) if cls == 14 else 1e-3
                kw.update(nB=nB, shade_prof=[[0, 1], [Tf, 1], [Tf + ramp, k], [10, k]])
                par = f'nB={nB};k={k:.3f};ramp={ramp:.3f}'
            elif cls == 16:
                sg = np.ones(3); ph = int(rng.integers(3)); sg[ph] = 1 - rng.uniform(.1, .3)
                kw['sens_gain'] = sg; par = f'phase={ph};gain={sg[ph]:.3f}'
            elif cls == 17:
                d = rng.uniform(.1, .5); kw.update(sag_step=-d, sag_dur=10.0); par = f'depth={d:.3f}'
            G0 = Gp[0][1]
            rows.append(dict(run=n, cls=cls, group=GROUP[cls], group_name=GNAME[GROUP[cls]],
                             switch_id=cls if 1 <= cls <= 12 else 0, profile=p + 1, G0=G0, T=T,
                             Tf=round(Tf, 6), params=par, kw=kw))
    return rows

def do(r):
    f = os.path.join(OUT, f"run_{r['run']:03d}.npz")
    if os.path.exists(f): return r['run'], 'skipped', 0.0
    t0 = time.time()
    try:
        L = run(**r['kw']); Tf = r['kw']['Tf']
        L = L[(L[:, 0] >= Tf - 0.2) & (L[:, 0] < Tf + 0.4)]
        np.savez_compressed(f + '.tmp.npz', data=L, cols=np.array(COLS), cls=r['cls'], group=r['group'], Tf=Tf)
        os.replace(f + '.tmp.npz', f)
        return r['run'], 'ok', time.time() - t0
    except Exception as e:
        return r['run'], f'error: {e}', time.time() - t0

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    rows = plan()
    if '--pilot' in sys.argv:
        rows = [r for r in rows if r['profile'] in (3, 18) and (r['profile'] == 3 or r['cls'] in (0, 14))]
    if '--sample' in sys.argv:   # one run per class: profile 14 (1000 W/m2, 30 degC)
        rows = [r for r in rows if r['profile'] == 14]
    with open(os.path.join('dataset', 'labels.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, [k for k in rows[0] if k != 'kw']); w.writeheader()
        for r in rows: w.writerow({k: v for k, v in r.items() if k != 'kw'})
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else max(os.cpu_count() - 1, 1)
    run(Tstop=0.01)  # compile once
    t0 = time.time()
    with Pool(nw) as pool, open(os.path.join('dataset', 'run_log.csv'), 'a', newline='') as lg:
        for k, (n, st, dt) in enumerate(pool.imap_unordered(do, rows), 1):
            csv.writer(lg).writerow([n, st, f'{dt:.2f}']); lg.flush()
            print(f'[{k}/{len(rows)}] run {n:03d} {st} {dt:.1f}s', flush=True)
    print(f'done: {len(rows)} runs in {(time.time() - t0) / 60:.1f} min')
