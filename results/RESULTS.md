# Results

All results were produced on a laptop CPU with the scripts in this repo (no MATLAB).

## 1. Dataset generation

| Item | Value |
|---|---|
| Runs | 360 (18 classes × 20 weather profiles), 0 errors |
| Time | **8.4 min** for all 360 runs (parallel); 20-run pilot 0.7 min |
| Size | 296 MB (`dataset/runs/*.npz`, float32, 20 kHz, 0.6 s window per run) |
| Tables | [`dataset/labels.csv`](../dataset/labels.csv), [`dataset/summary.csv`](../dataset/summary.csv), [`dataset/README.md`](../dataset/README.md) |

## 2. Model verification (`test_note.py`, [output](test_note.txt))

11 of 13 checks agree with the Simulink reference values. Healthy power, currents, Vdc, boost-open, shading, string-open and grid-sag all agree within 2 %.

The two mismatches are at low irradiance (200 W/m²: 16.7 vs 19.3 kW; 300 W/m²: 27.0 vs 30 kW). `pv_check.py` ([output](pv_check.txt)) solves the single-diode equation exactly with the module parameters of the Simulink PV block. It gives **100.4 kW at 273.5 V at 1000 W/m²**, the same as the reference, but only **16.7 kW at 200 W/m²** and **27.0 kW at 300 W/m²**. The reference values at low irradiance are therefore above the physical maximum of that PV array, and should be rechecked on the Simulink side (averaging window or cell temperature).

## 3. Random-forest baseline (`ml_baseline.py`, [output](ml_baseline.txt))

Setup: 2-cycle windows (666 samples) with a half-cycle stride, post-fault part of each run, 58 hand-crafted features per window (inverter and controller currents, Vab, DC link, PV side; irradiance and temperature not used). Splits are grouped by run, so no run appears in both train and test.

| Test | Inputs | 12 groups acc / F1 | 18 classes acc / F1 |
|---|---|---|---|
| T1 same weather (75/25 run split) | raw | 87.0 / 81.1 | 85.0 / 85.4 |
| T1 | normalised | 86.8 / 80.9 | 85.7 / 86.1 |
| T2 train 600–1000 → test 200–400 W/m² | raw | 79.3 / 67.2 | 51.2 / 57.9 |
| T2 | normalised | **88.9 / 79.2** | **75.7 / 72.4** |
| T3 fixed → changing weather | raw | 87.8 / 80.5 | 86.7 / 86.0 |
| T3 | normalised | 88.2 / 81.4 | 86.9 / 86.4 |

**Findings**
1. **Common-fundamental normalisation matters for unseen irradiance.** In T2, 18-class accuracy rises from 51 % to 76 % and 12-group accuracy from 79 % to 89 %.
2. **The 12 NPC switch faults are separable individually.** Recall for C01–C12 is 94–100 % in T1, and all 44 switch errors fall inside the S1/S2 or S3/S4 pair of the same leg. This agrees with the pairing physics in the progress note, but it shows that the pairs are *not* indistinguishable in this model, mainly because the line-voltage patterns differ.
3. **The real weak point is healthy vs partial shading vs string open (C00, C14, C15).** Recall is 45 %, 18 % and 1 % ([confusion matrix](confusion_T1_norm_18.csv)). After the transient, a shaded or partly lost array looks like a healthy array at lower irradiance. Window features alone cannot tell them apart without an irradiance reference or the fault transient itself. Boost-open, sensor-gain and grid-sag faults are classified at 100 %.

**Suggested next steps:** use G as a reference input (expected vs actual power), or add a transient-based detector for C14/C15. Also compare these numbers with the same baseline on the Simulink dataset once it is generated.
