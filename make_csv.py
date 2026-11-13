"""Spreadsheet-friendly CSVs of the dataset:
dataset_csv/dataset_overview.csv  one row per run (labels + key values)
dataset_csv/dataset_features.csv  one row per 2-cycle window (features + labels), same features as ml_baseline.py"""
import os, csv, numpy as np
from ml_baseline import feats, WIN, STRIDE

names = []
for src in ('Iinv', 'Imeas'):
    for ph in 'abc':
        names += [f'{src}_{ph}_{s}' for s in ('mean', 'std', 'max', 'min', 'fund', 'pos_frac', 'h2')]
    names += [f'{src}_fund_unbalance']
names += ['Vab_mean', 'Vab_std', 'Vab_pos_frac', 'Vab_neg_frac', 'Vdc_mean', 'Vdc_std', 'dVc_mean', 'dVc_std',
          'Vpv_mean', 'Vpv_std', 'D_mean', 'D_std', 'Ipv_ripple', 'Ipv_rel']
assert len(names) == 58

lab = {int(r['run']): r for r in csv.DictReader(open('dataset/labels.csv'))}
summ = {int(r['run']): r for r in csv.DictReader(open('dataset/summary.csv'))}
meta = ['run', 'cls', 'group', 'group_name', 'switch_id', 'profile', 'G0', 'T', 'Tf', 'params']

with open('dataset_csv/dataset_overview.csv', 'w', newline='') as fh:
    keys = meta + ['samples', 'P_pre_kW', 'P_post_kW', 'Vdc_post', 'Iinv_rms_pre', 'Iinv_rms_post', 'Ia_mean_post', 'file']
    w = csv.writer(fh); w.writerow(keys)
    for n in sorted(summ):
        r = {**lab[n], **summ[n]}; r['cls'] = lab[n]['cls']; r['file'] = 'dataset/' + r['file']; w.writerow([r[k] for k in keys])

nrow = 0
with open('dataset_csv/dataset_features.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['run', 'window', 't_start_after_fault_s', 'cls', 'group', 'group_name', 'profile', 'G0', 'T'] + names)
    for n in sorted(lab):
        f = f'dataset/runs/run_{n:03d}.npz'
        if not os.path.exists(f): continue
        z = np.load(f); D = z['data']; c = {k: i for i, k in enumerate(z['cols'])}; Tf = float(z['Tf'])
        D = D[D[:, 0] >= Tf + 0.02]; r = lab[n]
        for k, s in enumerate(range(0, len(D) - WIN, STRIDE)):
            v = feats(D[s:s + WIN], c, True)
            w.writerow([n, k, round(float(D[s, 0]) - Tf, 4), r['cls'], r['group'], r['group_name'], r['profile'], r['G0'], r['T']]
                       + [f'{x:.5g}' for x in v]); nrow += 1
print(f'dataset_overview.csv: {len(summ)} rows | dataset_features.csv: {nrow} rows x {len(names) + 9} cols')
