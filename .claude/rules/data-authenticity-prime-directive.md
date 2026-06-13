---
name: data-authenticity-prime-directive
description: 数据真实性最高准则 — 全系统所有数据必须真实、完整、来自正规渠道。禁止任何形式的假数据、人造数据、测试数据
metadata:
  type: project
---

# 数据真实性最高准则

## 一、核心原则

**数据是趋势跟随系统的根基。没有真实完整的数据，所有指标、趋势判定、推荐策略都是垃圾。**

本规则优先级高于所有其他规则。任何情况下不得违反。

## 二、合法数据源白名单

| 数据 | 唯一合法来源 | 存储位置 |
|------|-------------|---------|
| ETF日线 | akshare | `data/etf_stocks/etf_{code}.pkl` |
| 个股日线 | akshare | `data/massive_stocks/{code}.pkl` |
| 板块数据 | akshare | `dashboard/data/sector_*.parquet` |
| 指数数据 | akshare | 由 `build_nav_index.py` 拉取 |
| 操作建议 | pipeline评分 | `actions_{date}.json` |
| 股票名称 | akshare | `data/stock_names.json` |

**不在此白名单的数据源一律禁止。**

## 三、严禁使用的假数据

1. ❌ Parquet转pkl — 无日期列，索引对齐是猜测，价格错位
2. ❌ 手工创建空JSON — `{"etf_top5":[]}`，没有真实评分
3. ❌ 硬编码默认列表 — 不随市场变化
4. ❌ 复制HTML/JSON改名 — 日期/导航/数据全错乱
5. ❌ 只下载部分股票 — 必须全量（剔除ST/退市后约4500只）
6. ❌ 扫描设上限 — 必须扫描全部标的
7. ❌ 接受数据量不足 — 4000+=全量，800≠全量
8. ❌ 下载ST/退市股票 — 涨跌幅5%、退市风险，不适合趋势跟随

## 四、数据真伪检测

```python
def verify_pkl(path):
    df = pickle.load(open(path, 'rb'))
    # 真数据：有amount或turnover列，>1000行
    if 'amount' not in df.columns and 'turnover' not in df.columns:
        return False  # 疑似parquet假数据
    if len(df) < 1000:
        return False  # 数据量不足
    return True
```

## 五、历史错误清单（12条）

| # | 错误 | 后果 |
|---|------|------|
| 1 | Parquet→pkl，日期对齐错误 | 时代电气假趋势，评分93 |
| 2 | 手工创建空actions JSON | 无评分无建议 |
| 3 | 硬编码5只新能源ETF | 全下跌，行业重叠 |
| 4 | 只下载5只股票 | 真数据仅5只 |
| 5 | 复制HTML改名 | 侧边栏丢失 |
| 6 | 扫描设200上限 | 只扫1/4候选池 |
| 7 | 接受805只当全量 | 没质疑为何不是5000+ |
| 8 | 手工改dashboard_data.date | 与date_nav不同步 |
| 9 | 用`#`当个股链接 | 点不开落地页 |
| 10 | 板块/龙头数据填空 | 侧边栏无信息 |
| 11 | ETF用天天基金链接 | 无K线图 |
| 12 | parquet假数据占96% | 整个个股池是假的 |

**这12条全部指向同一个根因：选择了捷径而不是数据完整性。**

## 六、每日强制检查

```bash
python3 -c "
import os, pickle
etf_count = len([f for f in os.listdir('data/etf_stocks') if f.endswith('.pkl')])
stock_files = [f for f in os.listdir('data/massive_stocks') if f.endswith('.pkl')]
assert etf_count >= 130, f'ETF不足: {etf_count}'
assert len(stock_files) >= 4000, f'个股不足: {len(stock_files)}'
# 抽查真伪
fake = 0
for f in stock_files[:100]:
    df = pickle.load(open(f'data/massive_stocks/{f}', 'rb'))
    if 'amount' not in df.columns and 'turnover' not in df.columns:
        fake += 1
assert fake == 0, f'发现假数据{fake}/100!'
print('✅ 数据真实完整')
"
```
