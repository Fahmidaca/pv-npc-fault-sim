"""Excel versions of dataset_csv/*.csv (bold header, frozen top row, filters, sized columns)."""
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
for name in ('dataset_overview', 'dataset_features'):
    rows = list(csv.reader(open(f'dataset_csv/{name}.csv')))
    wb = Workbook(); ws = wb.active; ws.title = name.replace('dataset_', '')
    def num(v):
        try: return int(v)
        except ValueError:
            try: return float(v)
            except ValueError: return v
    ws.append(rows[0])
    for r in rows[1:]: ws.append([num(v) for v in r])
    for c in ws[1]: c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='305496')
    ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
    for i, h in enumerate(rows[0], 1):
        w = max(len(h), *(len(r[i - 1]) for r in rows[1:200])) + 2
        ws.column_dimensions[get_column_letter(i)].width = min(w, 40)
    wb.save(f'dataset_csv/{name}.xlsx'); print(name, len(rows) - 1, 'rows')
