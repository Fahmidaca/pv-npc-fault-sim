# Dataset as spreadsheet CSVs

Spreadsheet-friendly copies of the dataset (Excel / Google Sheets). Built by `../make_csv.py` from `../dataset/`.

| File | Rows × cols | Content |
|---|---|---|
| [dataset_overview.csv](dataset_overview.csv) | 360 × 18 | One row per run: class, group, switch, weather profile, G, T, Tf, fault parameters, PV power before/after the fault, Vdc, inverter current rms, waveform file |
| [dataset_features.csv](dataset_features.csv) | 15 120 × 67 | One row per 2-cycle window (post-fault, half-cycle stride): run, class, group, weather + 58 named features (normalised by the common fundamental). This is the table `ml_baseline.py` trains on |

Excel versions with a bold header, frozen top row and filters: [dataset_overview.xlsx](dataset_overview.xlsx) and [dataset_features.xlsx](dataset_features.xlsx). Built by `../make_xlsx.py`.

The raw waveforms (4.3 M samples × 22 channels) are in `../dataset/runs/*.npz`; they are too large for a spreadsheet.
