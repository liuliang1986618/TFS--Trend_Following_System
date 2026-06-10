# 全量市场数据下载最高准则

## 一、核心原则

**系统中的每一个数据维度——ETF、个股、行业板块、概念题材——都必须从市场实时拉取全量数据。不允许硬编码数量、不允许假设数量、不允许设置任何上限。**

## 二、四个全量维度

| 维度 | 数据源 | 获取 API | 说明 |
|------|--------|---------|------|
| ETF | 全市场 ETF | `ak.fund_etf_spot_em()` | ~1500 只，动态变化，不固定 |
| 个股 | 全市场 A 股（剔除 ST/退市） | `ak.stock_info_a_code_name()` → 过滤 ST | ~4500 只，动态变化，不固定 |
| 行业板块 | 东方财富行业板块 | `ak.stock_board_industry_name_em()` | 动态变化，不固定 |
| 概念题材 | 东方财富概念板块 | `ak.stock_board_concept_name_em()` | ~400 个，动态变化，不固定 |

**这些数量不是固定值。市场每天都有新 ETF 上市、旧 ETF 退市、股票 ST/摘帽。必须每次从 API 实时获取最新列表，禁止引用缓存数量。**

## 三、绝对禁止（红线）

1. ❌ **硬编码 ETF 列表** — 如 `ETF_NAME_MAP` 只包含 157 只 ETF，导致 90% ETF 未被覆盖
1.5 ❌ **硬编码 ETF 名称映射** — `ETF_NAME_MAP` 静态157条，新ETF名称缺失时页面显示 "ETF159153"。必须使用 `ak.fund_etf_spot_em()` 全量拉取 → `data/etf_names.json` 缓存（当前1503只）
2. ❌ **设置任何扫描/下载/加载上限** — 如 `limit=2000`、`[:2000]`、`head(100)` 等
3. ❌ **臆想或假设数量** — 如"ETF 约 132 只就够了"，实际全市场有 1500+
4. ❌ **只更新已有文件，不发现新标的** — `_update_pkl_caches` 只遍历已有 pkl
5. ❌ **从 Part 2 开始分析** — 必须先有全量 Part 1 原始数据
6. ❌ **接受数据量不足** — 个股<4000 或 ETF<1000 说明下载未完成，不得继续

## 四、正确模式 vs 错误模式

### ETF 下载

```python
# ✅ 正确：从 akshare 动态获取全量列表
etf_list = ak.fund_etf_spot_em()
for code in etf_list["代码"].astype(str):
    download_one_etf(code)

# ❌ 错误：硬编码列表
ETF_NAME_MAP = {"510050": "...", ...}  # 只有 145 只！

# ❌ 错误：只更新已有文件
for fname in os.listdir("data/etf_stocks"):  # 永不会增加新 ETF
    update_only(fname)
```

### 个股下载

```python
# ✅ 正确：全量下载，不设上限
stock_list = ak.stock_info_a_code_name()
normal = stock_list[~stock_list["name"].str.contains("ST|退", na=False)]
for code in normal["code"]:
    download_one_stock(code)

# ❌ 错误：设置上限
stocks = load_cached_stocks(limit=2000)    # 只加载 2000 只
scanner.scan_stocks(date, limit=2000)      # 只扫描 2000 只
_update_pkl_caches(date, stock_limit=2000) # 只更新 2000 只
```

### 板块/题材

```python
# ✅ 正确：动态获取
sectors = ak.stock_board_industry_name_em()   # 全量行业
concepts = ak.stock_board_concept_name_em()    # 全量题材

# ❌ 错误：硬编码列表或数量
SECTOR_LIST = ["新能源", "半导体", ...]  # 静态列表，不随市场更新
```

## 五、受影响代码位置

| 文件 | 行号 | 问题 | 修复 |
|------|------|------|------|
| `src/fusion/scanner.py` | 17-96 | `ETF_NAME_MAP` 硬编码 145 只 | 改为从 `ak.fund_etf_spot_em()` 动态获取 + 缓存 |
| `src/enhanced_actions.py` | `_scan_best_etfs` | ETF_NAME_MAP 只157条，大量名称缺失 | 优先读 `data/etf_names.json`（akshare全量缓存） |
| `pipeline.py` | 45 | `load_cached_stocks(limit=2000)` | 移除 limit 参数，全量加载 |
| `pipeline.py` | 52 | `files[:limit]` | 移除切片 |
| `pipeline.py` | 191 | `_update_pkl_caches(stock_limit=2000)` | 移除 stock_limit，全量更新 |
| `pipeline.py` | 233 | `stock_files[:stock_limit]` | 移除切片 |
| `pipeline.py` | 472,646 | `scan_stocks(limit=2000)` | 移除 limit，全量扫描 |
| `pipeline.py` | 631 | `load_cached_stocks(limit=2000)` | 移除 limit |
| `pipeline.py` | 202 | 只遍历已有 ETF pkl | 新增 ETF 发现逻辑：对比 `ak.fund_etf_spot_em()` 列表 |

## 六、改动后强制验证

```bash
python3 -c "
import akshare as ak, os, re

# ETF 全量
etf_list = ak.fund_etf_spot_em()
etf_codes = set(etf_list['代码'].astype(str))
pkl_etfs = set(f.replace('etf_','').replace('.pkl','')
               for f in os.listdir('data/etf_stocks') if f.endswith('.pkl'))
missing = etf_codes - pkl_etfs
print(f'ETF: pkl={len(pkl_etfs)} 市场={len(etf_codes)} 缺失={len(missing)}')
if len(missing) > len(etf_codes) * 0.2:
    print('  ⚠️ 缺失>20%，需补下载')

# ETF 名称缓存
if os.path.exists('data/etf_names.json'):
    etf_names = json.load(open('data/etf_names.json'))
    print(f'ETF名称缓存: {len(etf_names)} 只')
else:
    print('  ❌ data/etf_names.json 缺失！需从 akshare 重新生成')

# 个股全量
stock_list = ak.stock_info_a_code_name()
normal = stock_list[~stock_list['name'].str.contains('ST|退', na=False)]
stock_codes = set(normal['code'].astype(str).str.zfill(6))
pkl_stocks = set(f.replace('.pkl','') for f in os.listdir('data/massive_stocks') if f.endswith('.pkl'))
missing_s = stock_codes - pkl_stocks
print(f'个股: pkl={len(pkl_stocks)} 市场={len(stock_codes)} 缺失={len(missing_s)}')

# 代码无硬编码 limit
for fpath in ['pipeline.py', 'src/enhanced_actions.py']:
    with open(fpath) as f:
        code = f.read()
    limits = re.findall(r'limit\s*=\s*\d+', code)
    if limits: print(f'  ❌ {fpath} 仍有 limit: {limits}')
    else: print(f'  ✅ {fpath} 无硬编码 limit')
print('✅ 全量检查完成')
"
```

## 七、与现有规则的关系

本规则确保数据源的全量覆盖，与以下规则配合：
- [[data-authenticity-prime-directive]] — 数据真实性（pkl 正源 vs Parquet 缓存）
- [[full-market-data-integrity]] — 全量数据完整性（Part 1→2→3 不可跳跃）
- [[data-directory-standard]] — 按日期组织6层目录
- [[stock-screening-quality-gate]] — 全量扫描后的质量筛选
