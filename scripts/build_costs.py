# usage: python3 -I build_costs.py OUT.csv cost1.xlsx [cost2.xlsx ...]
# 온라인팀 마감내역(거래처별 공제 비용·물류비) 엑셀의 첫 시트를 읽어 월·거래처별 표로 만든다.
# 같은 달 파일이 여러 개면 나중 파일이 덮어쓴다. 금액은 VAT 별도.
import sys, re, warnings
import openpyxl, pandas as pd
warnings.filterwarnings('ignore')

out = sys.argv[1]
by_month = {}
for path in sys.argv[2:]:
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    hdr_r = next(r for r in range(1, 15) if any(ws.cell(r, c).value == '거래처명' for c in range(1, 10)))
    name_c = next(c for c in range(1, 10) if ws.cell(hdr_r, c).value == '거래처명')
    top = {str(ws.cell(hdr_r, c).value or '').strip(): c for c in range(1, ws.max_column + 1)}
    sub = {str(ws.cell(hdr_r + 1, c).value or '').strip(): c for c in range(1, ws.max_column + 1)}
    sales_c = top['매출액 (출고기준)']
    cur_c = sales_c + 1                      # 매출액 두 칸 중 오른쪽 = 이번 달
    m = re.match(r'(\d{4})년\s*(\d{1,2})월', str(ws.cell(hdr_r + 1, cur_c).value))
    month = f'{m.group(1)}-{int(m.group(2)):02d}'
    col = {'수수료': sub['수수료'], '광고비': sub['광고비'], '판촉비': sub['판촉비'], '장려금외': sub['장려금 외'],
           '공제합계': sub['공제 합계'], '물류비': top['물류비'], '비고': top['비고']}
    rows = []
    r = hdr_r + 2
    while r <= ws.max_row:
        n = ws.cell(r, name_c).value
        if n == '합계':
            total = {k: ws.cell(r, c).value for k, c in col.items() if k != '비고'}
            total['매출액'] = ws.cell(r, cur_c).value
            break
        if n:
            num = lambda c: float(ws.cell(r, c).value or 0) if isinstance(ws.cell(r, c).value, (int, float)) else 0.0
            row = {'월': month, '거래처': str(n).strip(), '매출액': num(cur_c)}
            for k, c in col.items():
                row[k] = (str(ws.cell(r, c).value).strip() if ws.cell(r, c).value else '') if k == '비고' else num(c)
            if any(row[k] for k in ['매출액', '공제합계', '물류비']):
                rows.append(row)
        r += 1
    df = pd.DataFrame(rows)
    chk = {k: round(df[k].sum()) - round(total[k] or 0) for k in ['매출액', '공제합계', '물류비']}
    print(month, path.split('/')[-1][:9], f'{len(df)}곳', '합계차이', chk, '(덮어씀)' if month in by_month else '')
    by_month[month] = df

all_ = pd.concat([by_month[k] for k in sorted(by_month)], ignore_index=True)
for k in ['매출액', '수수료', '광고비', '판촉비', '장려금외', '공제합계', '물류비']:
    all_[k] = all_[k].round(0).astype(int)
all_.to_csv(out, index=False, encoding='utf-8')
print('months', sorted(by_month), 'rows', len(all_))
print(all_.groupby('월')[['매출액', '공제합계', '물류비']].sum().to_string())
