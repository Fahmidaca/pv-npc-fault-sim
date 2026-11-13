"""Generates the README figures into figures/."""
import os, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from pvnpc import run, COLS
c = {n: k for k, n in enumerate(COLS)}; os.makedirs('figures', exist_ok=True)
plt.rcParams.update({'font.size': 9, 'axes.grid': True, 'grid.alpha': .3})

def win(L, a, b): w = (L[:, 0] >= a) & (L[:, 0] < b); return L[w]
def iabc(ax, L, key='Iinv', title=''):
    for p, col in zip('abc', ['C0', 'C1', 'C2']): ax.plot(L[:, 0], L[:, c[f'{key}_{p}']], col, lw=.8, label=p)
    ax.axvline(0.8, color='k', ls='--', lw=.8); ax.set_title(title); ax.set_ylabel('A')

# 1. healthy operation
L = run(Tstop=1.0); L = win(L, 0.05, 1.0)
f, ax = plt.subplots(4, 1, figsize=(8, 8))
ax[0].plot(L[:, 0], L[:, c['Vpv']] * L[:, c['Ipv']] / 1e3); ax[0].set_ylabel('kW'); ax[0].set_title('PV power')
ax[1].plot(L[:, 0], L[:, c['Vdc']], label='Vdc'); ax[1].plot(L[:, 0], L[:, c['vC1']], label='vC1'); ax[1].plot(L[:, 0], L[:, c['vC2']], label='vC2')
ax[1].set_ylabel('V'); ax[1].legend(loc='right'); ax[1].set_title('DC link')
ax[2].plot(L[:, 0], L[:, c['Vpv']]); ax[2].set_ylabel('V'); ax[2].set_title('PV voltage (MPPT)')
Z = win(L, 0.9, 0.95)
for p in 'abc': ax[3].plot(Z[:, 0], Z[:, c[f'Iinv_{p}']], lw=.8)
ax[3].set_title('Inverter current (zoom)'); ax[3].set_ylabel('A'); ax[3].set_xlabel('t (s)')
f.suptitle('Healthy operation, 1000 W/m², 25 °C'); f.tight_layout(); f.savefig('figures/healthy.png', dpi=130); plt.close(f)

# 2. switch faults S1a vs S2a vs S3a
f, ax = plt.subplots(3, 2, figsize=(10, 7), sharex=True)
for r, k in enumerate([0, 1, 2]):
    m = np.ones(12); m[k] = 0; L = win(run(gate_mask=m), 0.75, 0.9)
    iabc(ax[r, 0], L, title=f'S{k+1}a open: inverter current')
    ax[r, 1].plot(L[:, 0], L[:, c['Vab']], lw=.4); ax[r, 1].axvline(0.8, color='k', ls='--', lw=.8)
    ax[r, 1].set_title(f'S{k+1}a open: line voltage Vab'); ax[r, 1].set_ylabel('V')
ax[2, 0].set_xlabel('t (s)'); ax[2, 1].set_xlabel('t (s)')
f.suptitle('NPC open-switch faults at Tf = 0.8 s'); f.tight_layout(); f.savefig('figures/switch_faults.png', dpi=130); plt.close(f)

# 3. non-switch faults
cases = [('C13 boost open', dict(boost_on=0)),
         ('C14 shading (nB=26, 30 %)', dict(nB=26, shade_prof=[[0, 1], [.8, 1], [.9, .3], [10, .3]])),
         ('C15 string open (nB=20)', dict(nB=20, shade_prof=[[0, 1], [.8, 1], [.801, 0], [10, 0]])),
         ('C16 sensor gain (a = 0.8)', dict(sens_gain=[.8, 1, 1])),
         ('C17 grid sag 30 %', dict(sag_step=-0.3))]
f, ax = plt.subplots(len(cases), 3, figsize=(12, 11), sharex=True)
for r, (name, kw) in enumerate(cases):
    L = win(run(**kw), 0.7, 1.2)
    ax[r, 0].plot(L[:, 0], L[:, c['Vpv']] * L[:, c['Ipv']] / 1e3); ax[r, 0].set_ylabel('kW'); ax[r, 0].set_title(f'{name}: PV power')
    ax[r, 1].plot(L[:, 0], L[:, c['Vdc']]); ax[r, 1].set_ylabel('V'); ax[r, 1].set_title('Vdc')
    iabc(ax[r, 2], L, title='Inverter current')
    for a in ax[r, :2]: a.axvline(0.8, color='k', ls='--', lw=.8)
for a in ax[-1]: a.set_xlabel('t (s)')
f.tight_layout(); f.savefig('figures/other_faults.png', dpi=130); plt.close(f)
print('saved figures/healthy.png, switch_faults.png, other_faults.png')
