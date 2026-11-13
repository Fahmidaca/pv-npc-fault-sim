"""Random-forest baseline on the dataset (Next Steps 2-3 of the progress note).
2-cycle windows with a half-cycle stride, post-fault only, splits grouped by run.
T1: same weather (random run split)   T2: train 600-1000 W/m2, test 200-400 W/m2   T3: fixed -> changing weather."""
import os, csv, json, numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix

FS, F0 = 20000, 60
WIN, STRIDE = 2 * FS // F0, FS // F0 // 2          # 666 / 166 samples
CH = ['Iinv_a', 'Iinv_b', 'Iinv_c', 'Imeas_a', 'Imeas_b', 'Imeas_c', 'Vab', 'Vdc', 'vC1', 'vC2', 'Vpv', 'Ipv', 'D']

def fund(x):  # fundamental magnitude over the window (2 cycles -> FFT bin 2)
    return 2 * np.abs(np.fft.rfft(x - x.mean())[2]) / len(x)

def feats(w, c, norm):
    I = w[:, [c['Iinv_a'], c['Iinv_b'], c['Iinv_c']]]
    Im = w[:, [c['Imeas_a'], c['Imeas_b'], c['Imeas_c']]]
    s = np.mean([fund(I[:, k]) for k in range(3)]) + 1e-6 if norm else 1.0   # common fundamental
    f = []
    for X in (I / s, Im / s):
        for k in range(3):
            x = X[:, k]; f += [x.mean(), x.std(), x.max(), x.min(), fund(x), np.mean(x > 0), 2 * np.abs(np.fft.rfft(x)[4]) / len(x)]
        f += [np.std([fund(X[:, k]) for k in range(3)])]
    vab = w[:, c['Vab']]; f += [vab.mean() / 500, vab.std() / 500, np.mean(vab > 0), np.mean(vab < 0)]
    vdc, v1, v2 = w[:, c['Vdc']], w[:, c['vC1']], w[:, c['vC2']]
    f += [vdc.mean() / 500, vdc.std() / 500, (v1 - v2).mean() / 500, (v1 - v2).std() / 500]
    vpv, ipv, d = w[:, c['Vpv']], w[:, c['Ipv']], w[:, c['D']]
    f += [vpv.mean() / 320, vpv.std() / 320, d.mean(), d.std(), ipv.std() / (abs(ipv.mean()) + 1),
          ipv.mean() / (s * 1.2 if norm else 366)]
    return f

def load(norm):
    lab = {int(r['run']): r for r in csv.DictReader(open('dataset/labels.csv'))}
    X, y, g, run = [], [], [], []
    for n, r in lab.items():
        f = f'dataset/runs/run_{n:03d}.npz'
        if not os.path.exists(f): continue
        z = np.load(f); D = z['data']; c = {k: i for i, k in enumerate(z['cols'])}; Tf = float(z['Tf'])
        D = D[D[:, 0] >= Tf + 0.02]          # post-fault, skip first ~1 cycle
        for s in range(0, len(D) - WIN, STRIDE):
            X.append(feats(D[s:s + WIN], c, norm)); y.append(int(r['cls'])); g.append(int(r['group'])); run.append(n)
    return np.array(X), np.array(y), np.array(g), np.array(run), lab

def split(test, lab, runs):
    rng = np.random.default_rng(0)
    if test == 'T1':
        te = set()
        for cl in range(18):
            rr = sorted(n for n, r in lab.items() if int(r['cls']) == cl)
            te |= set(rng.choice(rr, len(rr) // 4, replace=False).tolist())
        tr = set(lab) - te
    elif test == 'T2':
        fixed = lambda r: int(r['profile']) <= 15
        tr = {n for n, r in lab.items() if fixed(r) and float(r['G0']) >= 600}
        te = {n for n, r in lab.items() if fixed(r) and float(r['G0']) <= 400}
    else:
        tr = {n for n, r in lab.items() if int(r['profile']) <= 15}
        te = {n for n, r in lab.items() if int(r['profile']) > 15}
    return np.isin(runs, list(tr)), np.isin(runs, list(te))

if __name__ == '__main__':
    res = {}
    for norm in (False, True):
        X, y, g, runs, lab = load(norm)
        for test in ('T1', 'T2', 'T3'):
            tr, te = split(test, lab, runs)
            for target, Y in (('12 groups', g), ('18 classes', y)):
                m = RandomForestClassifier(300, n_jobs=-1, random_state=0).fit(X[tr], Y[tr])
                p = m.predict(X[te]); key = f"{test} | {'norm' if norm else 'raw '} | {target}"
                res[key] = dict(acc=accuracy_score(Y[te], p), f1=f1_score(Y[te], p, average='macro'),
                                n_train=int(tr.sum()), n_test=int(te.sum()))
                print(f"{key:32s} acc {res[key]['acc']*100:5.1f} %  macro-F1 {res[key]['f1']*100:5.1f} %  "
                      f"(train {tr.sum()} / test {te.sum()} windows)", flush=True)
                if test == 'T1' and target == '18 classes' and norm:
                    cm = confusion_matrix(Y[te], p, labels=range(18))
                    sw = cm[1:13, 1:13]; pair = sum(sw[i, i ^ 1] for i in range(12))
                    off = sw.sum() - np.trace(sw)
                    res['switch_confusion'] = dict(total_offdiag=int(off), within_pair=int(pair))
                    np.savetxt('results/confusion_T1_norm_18.csv', cm, fmt='%d', delimiter=',')
    json.dump(res, open('results/ml_baseline.json', 'w'), indent=1)
    print('switch confusion (T1, 18 classes):', res.get('switch_confusion'))
