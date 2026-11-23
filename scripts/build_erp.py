# usage: python3 -I build_v2.py OUT_DIR erp1.xlsx [erp2.xlsx ...]   (기간이 겹치면 앞 파일이 그 기간을 대신함: 최신 파일을 앞에)
# ERP 일일판매실적 엑셀(비표준 xlsx)을 읽어 대시보드용 CSV 4개를 만든다.
#   sales.csv   일, 거래처, 담당자, 품번, 수량, 매출액(VAT 제외)
#   prices.csv  일, 거래처, 품번, 단가(VAT 제외), 단가VAT, 수량   (수량>0, 금액>0 줄만)
#   clients.csv 거래처, 채널, 담당자
#   skus.csv    품번, 품명, 카테고리
import sys, os, io, zipfile, xml.etree.ElementTree as ET
import pandas as pd

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def ci(s):
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_erp(path):
    z = zipfile.ZipFile(path)
    name = [n for n in z.namelist() if n.startswith('xl/worksheets/') and n.endswith('.xml')][0]
    # 일반 엑셀로 저장된 파일은 글자를 공유 문자열 표(sharedStrings)에 따로 둔다
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(NS + 'si'):
            shared.append(''.join(t.text or '' for t in si.iter(NS + 't')))
    rows = []
    for ev, el in ET.iterparse(io.BytesIO(z.read(name))):
        if el.tag == NS + 'row':
            d = {}
            for c in el.findall(NS + 'c'):
                col = ''.join(ch for ch in c.get('r') if ch.isalpha())
                t = c.find(NS + 'is'); v = c.find(NS + 'v')
                val = ''.join(t.itertext()) if t is not None else (v.text if v is not None else None)
                if c.get('t') == 's' and val not in (None, ''):
                    val = shared[int(val)]
                elif c.get('t') in ('n', None) and val not in (None, ''):
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                d[ci(col)] = val
            rows.append(d); el.clear()
    mx = max(max(r) for r in rows if r) + 1
    data = [[r.get(i) for i in range(mx)] for r in rows]
    hdr_i = next(i for i, r in enumerate(data) if '수출구분' in [str(x) for x in r])
    hdr = [h or f'col{i}' for i, h in enumerate(data[hdr_i])]
    df = pd.DataFrame(data[hdr_i + 1:], columns=hdr)
    df['_src'] = os.path.basename(path)
    return df


out = sys.argv[1]
os.makedirs(out, exist_ok=True)
frames, covered, before = [], [], 0
for path in sys.argv[2:]:
    f = read_erp(path)
    f = f[f['수출구분'] == '내수'].copy()
    before += len(f)
    d = pd.to_datetime(f['실적구분일자']).dt.strftime('%Y-%m-%d')
    # 파일끼리 기간이 겹치면 앞(최신) 파일이 그 기간을 통째로 대신한다(뒤 파일의 같은 기간 줄은 뺀다)
    keep = pd.Series(True, index=f.index)
    for a, b in covered:
        keep &= ~((d >= a) & (d <= b))
    if len(f):
        covered.append((d.min(), d.max()))
    frames.append(f[keep])
df = pd.concat(frames, ignore_index=True)
for c in ['수량', '원화판매금액', '원화판매금액계']:
    df[c] = pd.to_numeric(df[c]).fillna(0)
df['일'] = pd.to_datetime(df['실적구분일자']).dt.strftime('%Y-%m-%d')
# 25년 파일은 '쿠팡(대표)' 아래에 '쿠팡 직매입'·'쿠팡'이 묶여 있어 실제 거래처 열을 쓴다(26년은 둘이 같음)
df['거래처'] = df['거래처'].fillna(df['대표거래처']).astype(str)
df['담당자'] = df['담당자'].fillna('').astype(str)

s = (df.groupby(['일', '거래처', '담당자', '품번'], dropna=False)
       .agg(수량=('수량', 'sum'), 매출액=('원화판매금액', 'sum')).reset_index())
s['수량'] = s['수량'].round(0).astype(int); s['매출액'] = s['매출액'].round(0).astype(int)
for y, part in s.groupby(s['일'].str[:4]):
    part.to_csv(f'{out}/sales_{y}.csv', index=False, encoding='utf-8')

pr = df[(df['수량'] > 0) & (df['원화판매금액'] > 0)].copy()
pr['단가'] = (pr['원화판매금액'] / pr['수량']).round(0).astype(int)
pr['단가VAT'] = (pr['원화판매금액계'] / pr['수량']).round(0).astype(int)
p = pr.groupby(['일', '거래처', '품번', '단가', '단가VAT']).agg(수량=('수량', 'sum')).reset_index()
p['수량'] = p['수량'].round(0).astype(int)
for y, part in p.groupby(p['일'].str[:4]):
    part.to_csv(f'{out}/prices_{y}.csv', index=False, encoding='utf-8')

# 채널·담당자는 거래처의 가장 최근 실적 줄 기준(담당자가 바뀐 거래처는 현재 담당자로 본다)
last = lambda x: next((v for v in reversed(list(x)) if v), '')
cl = df.sort_values('일').groupby('거래처').agg(채널=('유형세부', last), 담당자=('담당자', last)).reset_index()
cl.to_csv(f'{out}/clients.csv', index=False, encoding='utf-8')

# 품명·카테고리는 가장 최근 줄 기준
sk = (df.sort_values('일').groupby('품번').agg(품명=('품명', 'last'), 카테고리=('품목중분류', 'last')).reset_index())
sk.to_csv(f'{out}/skus.csv', index=False, encoding='utf-8')

months = sorted(df['일'].str.slice(0, 7).unique())
print(f'ERP 줄 {before:,} → 중복 제거 후 {len(df):,}')
print(f'sales {len(s):,}행 / prices {len(p):,}행 / 거래처 {len(cl)} / SKU {len(sk)}')
print('기간', df['일'].min(), '~', df['일'].max(), '| 월', months)
print('매출 합계', int(df['원화판매금액'].sum()))
for f in sorted(os.listdir(out)):
    print(f, os.path.getsize(f'{out}/{f}'), 'bytes')
