"""input/ 폴더의 엑셀로 data/ 폴더(대시보드가 읽는 CSV)를 다시 만든다.

  input/erp/    ERP 일일판매실적 엑셀 (기간이 겹치면 더 최근에 받은 파일이 그 기간을 대신함)
  input/costs/  온라인팀 월 마감내역 엑셀 (같은 달 파일이 여러 개면 더 최근에 받은 파일을 씀)

'더 최근에 받은 파일'은 파일 이름 속 14자리 다운로드 시각(예: Excel_20261123180857),
없으면 GitHub에 올린 시각(git 커밋 시각)으로 판단한다.

실행: python scripts/build_all.py
"""
import glob, json, os, re, subprocess, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
PY = sys.executable


def received_at(path):
    m = re.search(r'(20\d{12})', os.path.basename(path))
    if m:
        return int(datetime.datetime.strptime(m.group(1), '%Y%m%d%H%M%S').timestamp())
    try:
        out = subprocess.run(['git', 'log', '-1', '--format=%ct', '--', path], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if out:
            return int(out)
    except Exception:
        pass
    return int(os.path.getmtime(path))


def xlsx(folder):
    return [p for p in glob.glob(os.path.join(ROOT, 'input', folder, '*.xlsx')) if not os.path.basename(p).startswith('~$')]


erp = sorted(xlsx('erp'), key=received_at, reverse=True)      # 최신 파일 먼저
costs = sorted(xlsx('costs'), key=received_at)                 # 오래된 것부터 → 같은 달은 최신이 덮어씀
if not erp:
    sys.exit('input/erp 폴더에 ERP 엑셀이 없습니다.')

os.makedirs(DATA, exist_ok=True)
for f in glob.glob(os.path.join(DATA, '*.csv')):
    os.remove(f)

print('ERP 파일 (최신 순):', *[os.path.basename(p) for p in erp], sep='\n  ')
subprocess.run([PY, '-I', os.path.join(ROOT, 'scripts', 'build_erp.py'), DATA, *erp], check=True)
if costs:
    print('마감내역 파일:', *[os.path.basename(p) for p in costs], sep='\n  ')
    subprocess.run([PY, '-I', os.path.join(ROOT, 'scripts', 'build_costs.py'), os.path.join(DATA, 'costs.csv'), *costs], check=True)

rel = lambda f: 'data/' + os.path.basename(f)
datasets = {
    'sales': [rel(f) for f in sorted(glob.glob(os.path.join(DATA, 'sales_*.csv')))],
    'prices': [rel(f) for f in sorted(glob.glob(os.path.join(DATA, 'prices_*.csv')))],
    'clients': ['data/clients.csv'],
    'skus': ['data/skus.csv'],
}
if os.path.exists(os.path.join(DATA, 'costs.csv')):
    datasets['costs'] = ['data/costs.csv']
kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
manifest = {
    'updated_kst': kst.strftime('%Y-%m-%d %H:%M (KST)'),
    'erp_files': [os.path.basename(p) for p in erp],
    'cost_files': [os.path.basename(p) for p in costs],
    'datasets': datasets,
}
with open(os.path.join(DATA, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print('완료:', json.dumps(datasets, ensure_ascii=False))
