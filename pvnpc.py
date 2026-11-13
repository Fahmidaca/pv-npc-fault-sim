"""Python (numba) switching model of the 100-kW PV + boost + 3-level NPC grid inverter.
Re-implementation of pv_npc_fault.slx (not the Simulink model itself)."""
import numpy as np
from numba import njit

# ---- plant parameters (taken from pv_npc_fault.slx) ----
NSER, NSTR = 5, 66                       # 5 modules in series, 66 strings
NCELL, VOC, ISC, IL0, I00, NI, RSH, RS = 96, 64.2, 5.96, 6.0092, 6.3014e-12, 0.94504, 269.5934, 0.37152
A_ISC, B_VOC = 0.061745e-2, -0.27269e-2  # per degC
CPV, LB, RLB, FSW = 100e-6, 5e-3, 5e-3, 5000.0
C1 = C2 = 12e-3; VDCREF = 500.0
LF, RF = 250e-6, 500e-6 * 377 / 50 / 2   # inverter choke
ZB = 260.0**2 / 100e3
LT, RT = 0.06 * ZB / 377, 0.002 * ZB     # transformer leakage (both windings, 260 V side)
CF = 10e3 / (377 * 240.0**2)             # 10 kvar bank
VPK = 260.0 * np.sqrt(2 / 3); W = 2 * np.pi * 60; FC = 33 * 60.0
KT = 25000.0 / 260.0                     # turns ratio
DT, TSC, DEC = 1e-6, 100e-6, 50          # power step, control step, log every 50 -> 20 kHz


@njit(cache=True)
def i_string(v, G, T, i0):
    """Current of one string of 5 modules (single-diode, Newton)."""
    vm = v / NSER
    vt = NI * NCELL * 1.380649e-23 * (T + 273.15) / 1.602177e-19
    il = IL0 * G / 1000.0 * (1 + A_ISC * (T - 25))
    voc = VOC * (1 + B_VOC * (T - 25))
    i0s = ISC * (1 + A_ISC * (T - 25)) / (np.exp(voc / vt) - 1)
    i = i0
    for _ in range(4):
        e = np.exp(min((vm + i * RS) / vt, 80.0))
        f = il - i0s * (e - 1) - (vm + i * RS) / RSH - i
        df = -i0s * e * RS / vt - RS / RSH - 1
        i -= f / df
    return i


@njit(cache=True)
def sim(Gp, Tp, Sp, nB, Tf, Tstop, gmask, boost_on, sgain, sag, sag_dur, seed):
    n = int(Tstop / DT); nlog = n // DEC
    log = np.zeros((nlog, 22), np.float32)
    np.random.seed(seed)
    # states
    vpv, iL, v1, v2 = 273.0, 366.0, 250.0, 250.0
    i = np.zeros(3); ig = np.zeros(3)
    vc = np.array([VPK, VPK * np.cos(-2 * np.pi / 3), VPK * np.cos(2 * np.pi / 3)])
    ia_str, ib_str = 5.5, 5.5
    D, th, wpll, xpll = 0.45, 0.0, W, 0.0
    xid, xd, xq = 310.0, 0.0, 0.0
    m = np.zeros(3); st = np.zeros(3, np.int64); vleg = np.zeros(3)
    # MPPT averaging (one 60-Hz cycle)
    nwin = int(round(1 / 60 / TSC)); bufV = np.full(nwin, 273.0); bufI = np.full(nwin, 366.0)
    sV, sI, k, Vold, Iold = 273.0 * nwin, 366.0 * nwin, 0, 273.0, 366.0
    ph = np.array([0.0, -2 * np.pi / 3, 2 * np.pi / 3])
    nctl = int(TSC / DT); ipv = 0.0; Iinv_meas = np.zeros(3)
    for s in range(n):
        t = s * DT
        flt = t >= Tf
        G = np.interp(t, Gp[:, 0], Gp[:, 1]); T = np.interp(t, Tp[:, 0], Tp[:, 1])
        shade = np.interp(t, Sp[:, 0], Sp[:, 1])
        # ---------------- control (100 us) ----------------
        if s % nctl == 0:
            amp = VPK * (1 + (sag if (flt and t < Tf + sag_dur) else 0.0))
            # Clarke/Park of capacitor-node voltage (B1 measurement)
            va = (2 * vc[0] - vc[1] - vc[2]) / 3; vb = (vc[1] - vc[2]) / np.sqrt(3)
            vd = va * np.cos(th) + vb * np.sin(th); vq = -va * np.sin(th) + vb * np.cos(th)
            # PLL
            xpll += 50.0 * vq / VPK * TSC
            wpll = W + 300.0 * vq / VPK + 2e4 * xpll * TSC
            th = (th + wpll * TSC) % (2 * np.pi)
            # controller current = grid-side current x sensor gain
            Im = i.copy()
            if flt:
                for j in range(3): Im[j] *= sgain[j]
            Iinv_meas[:] = Im
            ia_ = (2 * Im[0] - Im[1] - Im[2]) / 3; ib_ = (Im[1] - Im[2]) / np.sqrt(3)
            id_ = ia_ * np.cos(th) + ib_ * np.sin(th); iq_ = -ia_ * np.sin(th) + ib_ * np.cos(th)
            # DC-voltage PI -> Id_ref
            e = (v1 + v2) - VDCREF
            xid += 30.0 * e * TSC
            idr = min(max(1.5 * e + xid, -500.0), 700.0)
            # current PI (dq) with decoupling
            Lt = LF + LT
            ed, eq = idr - id_, 0.0 - iq_
            xd += 400.0 * ed * TSC; xq += 400.0 * eq * TSC
            ud = vd + 1.0 * ed + xd - W * Lt * iq_
            uq = vq + 1.0 * eq + xq + W * Lt * id_
            vdc2 = max((v1 + v2) / 2, 1.0)
            for j in range(3):
                a = th + ph[j]
                m[j] = min(max((ud * np.cos(a) - uq * np.sin(a)) / vdc2, -1.0), 1.0)
            # MPPT: incremental conductance + integral regulator on 1-cycle means
            sV += vpv - bufV[k]; sI += ipv - bufI[k]; bufV[k] = vpv; bufI[k] = ipv; k = (k + 1) % nwin
            if t > 0.05:
                Vm, Imn = sV / nwin, sI / nwin
                dV, dI = Vm - Vold, Imn - Iold
                if abs(dV) > 1e-3 and Vm > 1:
                    err = dI / dV + Imn / Vm
                    D = min(max(D - 1.0 * err / (Imn / Vm + 1e-3) * TSC, 0.0), 0.9)
                Vold, Iold = Vm, Imn
        # ---------------- PV array ----------------
        nA = NSTR - nB
        ia_str = i_string(vpv, G, T, ia_str); ib_str = i_string(vpv, G * shade, T, ib_str)
        ipv = nA * ia_str + nB * ib_str
        # ---------------- boost ----------------
        car = (t * FSW) % 1.0
        sw = (D > car) and (boost_on > 0 or not flt)
        vdc = v1 + v2
        if sw:
            vl = vpv - RLB * iL
        else:
            vl = vpv - RLB * iL - vdc
        iL += vl / LB * DT
        if iL < 0: iL = 0.0
        ib = 0.0 if sw else iL
        vpv += (ipv - iL) / CPV * DT
        if vpv < -0.8: vpv = -0.8                      # bypass diode
        # ---------------- NPC legs (switching function with diodes) ----------------
        c = 1.0 - abs(2 * ((t * FC) % 1.0) - 1)        # triangle 0..1
        for j in range(3):
            if m[j] >= 0: cmd = 1 if m[j] > c else 0
            else: cmd = -1 if m[j] < c - 1 else 0
            g1 = cmd == 1; g2 = cmd >= 0; g3 = cmd <= 0; g4 = cmd == -1
            if flt:
                g1 = g1 and gmask[4 * j] > 0; g2 = g2 and gmask[4 * j + 1] > 0
                g3 = g3 and gmask[4 * j + 2] > 0; g4 = g4 and gmask[4 * j + 3] > 0
            if i[j] >= 0:   # current leaving leg
                st[j] = 1 if (g1 and g2) else (0 if g2 else -1)
            else:           # current entering leg
                st[j] = -1 if (g3 and g4) else (0 if g3 else 1)
            vleg[j] = v1 if st[j] == 1 else (-v2 if st[j] == -1 else 0.0)
        # ---------------- AC network (semi-implicit Euler) ----------------
        vn = 0.0
        for j in range(3): vn += vleg[j] - vc[j] - RF * i[j]
        vn /= 3
        for j in range(3):
            inew = i[j] + (vleg[j] - vn - vc[j] - RF * i[j]) / LF * DT
            if i[j] != 0 and inew * i[j] < 0: inew = 0.0   # diode commutation at zero
            i[j] = inew
        s0 = (i[0] + i[1] + i[2]) / 3
        for j in range(3): i[j] -= s0
        amp = VPK * (1 + (sag if (flt and t < Tf + sag_dur) else 0.0))
        vn2 = 0.0
        eg = np.zeros(3)
        for j in range(3):
            eg[j] = amp * np.cos(W * t + ph[j]); vn2 += vc[j] - eg[j] - RT * ig[j]
        vn2 /= 3
        for j in range(3): ig[j] += (vc[j] - vn2 - eg[j] - RT * ig[j]) / LT * DT
        for j in range(3): vc[j] += (i[j] - ig[j]) / CF * DT
        # ---------------- DC link ----------------
        iP = 0.0; iN = 0.0
        for j in range(3):
            if st[j] == 1: iP += i[j]
            elif st[j] == -1: iN += i[j]
        v1 += (ib - iP) / C1 * DT
        v2 += (ib + iN) / C2 * DT
        # ---------------- log (20 kHz) ----------------
        if s % DEC == 0 and s // DEC < nlog:
            r = log[s // DEC]
            r[0] = t; r[1:4] = i; r[4:7] = ig / KT; r[7:10] = Iinv_meas; r[10:13] = vc * KT
            r[13] = vleg[0] - vleg[1]; r[14] = v1 + v2; r[15] = v1; r[16] = v2; r[17] = vpv
            r[18] = vpv; r[19] = ipv; r[20] = G; r[21] = D
    return log

COLS = ['t', 'Iinv_a', 'Iinv_b', 'Iinv_c', 'Iabc_a', 'Iabc_b', 'Iabc_c', 'Imeas_a', 'Imeas_b', 'Imeas_c',
        'Vabc_a', 'Vabc_b', 'Vabc_c', 'Vab', 'Vdc', 'vC1', 'vC2', 'vC3', 'Vpv', 'Ipv', 'G', 'D']


def run(G=1000, T=25, Gprof=None, Tprof=None, shade_prof=None, nB=20, Tf=0.8, Tstop=1.2,
        gate_mask=None, boost_on=1, sens_gain=(1, 1, 1), sag_step=0.0, sag_dur=10.0, seed=0):
    Gp = np.array(Gprof if Gprof is not None else [[0, G], [10, G]], float)
    Tp = np.array(Tprof if Tprof is not None else [[0, T], [10, T]], float)
    Sp = np.array(shade_prof if shade_prof is not None else [[0, 1], [10, 1]], float)
    gm = np.ones(12) if gate_mask is None else np.asarray(gate_mask, float)
    return sim(Gp, Tp, Sp, int(nB), Tf, Tstop, gm, int(boost_on), np.asarray(sens_gain, float),
               float(sag_step), float(sag_dur), int(seed))
