# PV-NPC Fault Simulator (Python)

A MATLAB-free switching simulator of a **100 kW grid-connected PV system with a boost converter and a three-level NPC inverter**, plus a reproducible fault-dataset generator for physics-guided fault diagnosis.

It re-implements the circuit of the MATLAB example `power_PVarray_grid_det` (as modified in `pv_npc_fault.slx`) in Python, compiled with numba. One 1.2 s simulation at a 1 µs step takes about 2 s.

## System modelled

| Stage | Model |
|---|---|
| PV array | 330 × SunPower SPR-305E (5 series × 66 strings), single-diode model, split into Array A (66 − nB strings) and Array B (nB strings) for shading/string faults, bypass diode |
| Boost | 5 mH, 5 kHz PWM, incremental-conductance MPPT with an integral regulator on 1-cycle means |
| DC link | C1 = C2 = 12 mF, 500 V reference |
| Inverter | 3-level NPC, 12 switches, level-shifted PWM at 1980 Hz, switching-function model with clamp/antiparallel diode paths (open-switch faults are physical) |
| Control | SRF-PLL, Vdc PI → Id ref, dq current PI with decoupling, Iq ref = 0, control at 100 µs |
| Grid | 250 µH choke, 10 kvar capacitor bank, 100 kVA 260 V/25 kV transformer leakage, 60 Hz stiff source with programmable sag |

## Fault classes (18) and diagnostic groups (12)

| Class | Fault | Group |
|---|---|---|
| C00 | Healthy | 0 |
| C01–C12 | NPC switch open (S1–S4 of legs a, b, c) | 1–6 (upper/lower pair per leg) |
| C13 | Boost switch open | 7 |
| C14 | Partial shading (13–40 strings, 20–60 % irradiance, 0.05–0.2 s ramp) | 8 |
| C15 | String open (4–20 strings darkened in 1 ms) | 9 |
| C16 | Current-sensor gain fault (one phase reads 10–30 % low) | 10 |
| C17 | Grid voltage sag (10–50 %) | 11 |

## Quick start

```bash
pip install numpy numba
python test_note.py                 # verification checks (~30 s)
python make_dataset.py --pilot      # 20-run pilot (~1 min)
python make_dataset.py              # full 360 runs (18 classes x 20 weather profiles)
```

The dataset generator:
- writes one file per run (`dataset_runs/run_001.npz` … `run_360.npz`), 0.2 s before to 0.4 s after the fault at 20 kHz, in float32;
- is crash-safe: re-running skips finished runs, and files are written atomically;
- is reproducible: run *n* uses seed 1000 + *n*;
- writes `labels.csv` (class, group, switch, profile, G, T, Tf, fault parameters) and `run_log.csv`;
- runs in parallel on all CPU cores but one.

Load a run:
```python
import numpy as np
d = np.load('dataset_runs/run_001.npz')
X, cols = d['data'], list(d['cols'])   # columns: t, Iinv_abc, Iabc_abc, Imeas_abc, Vabc, Vab, Vdc, vC1, vC2, vC3, Vpv, Ipv, G, D
```

## Verification

| Check | Python | Reference (Simulink) |
|---|---|---|
| Healthy PV power, 1000 W/m² 25 °C | 100.2 kW | 100.4 kW |
| Grid / inverter current peak | 3.24 A / 311 A | 3.29 A / 318 A |
| Vdc | 500 V | 500 V |
| Boost open: PV power / voltage | 0 kW / 320.6 V | 0 / 320.8 V |
| Shading nB = 26, 30 % | 71.2 kW | 72.4 kW |
| String open nB = 10 / 20 | 84.3 / 68.3 kW | 84.8 / 69.7 kW |
| 30 % sag current ratio | 1.428 | 1.423 |
| 200 W/m² | 16.7 kW | 19.3 kW |

The MPPT reaches the true maximum power point of the PV model at every irradiance. The difference at low irradiance comes from the shunt-resistance loss in the module parameters.

**S1 vs S2 open faults:** with explicit diode paths, an S2 open fault sends the positive half-cycle current to −Vdc/2, while an S1 open fault sends it only to the midpoint. The phase current differs by about 6 % and the line voltage by about 70 %, so the two faults may be separable.

## Limitations
- This is an independent re-implementation, not the Simulink model. Control gains are tuned here.
- The grid is a stiff source behind the transformer leakage impedance (no feeder or loads). The transformer is linear and the Δ-Y phase shift is ignored.
- No neutral-point balancing control and no protection trips are modelled.

## Files
- `pvnpc.py`: plant + controller model (`run(...)` returns a 20 kHz log array)
- `test_note.py`: verification checks
- `make_dataset.py`: dataset generator
