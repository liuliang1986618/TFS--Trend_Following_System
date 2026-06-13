---
name: data-directory-standard
description: 数据目录结构标准 — 按日期组织6层数据，/dates/{date}/ 下自包含完整快照，支持回测
metadata:
  type: project
---

# 数据目录结构标准

## 一、核心原则

**每天的数据是一个自包含快照。从原始行情到最终展示，6层数据逐级加工。任何一天打开即用，不依赖跨目录查找。**

## 二、三级漏斗

```
板块轮动（90+行业板块） → 题材热点（200-400概念板块） → 个股择优（Top5）
```

## 三、标准目录结构

```
data/dates/{YYYY-MM-DD}/
│
├── 0-raw/                            # 根基层：全市场原始行情
│   ├── etfs.json                     # 全量ETF OHLCV+MA+MACD+RSI+BB
│   └── stocks.parquet                # 全量个股 OHLCV+MA+MACD+RSI+BB
│
├── 1-market/                         # 市场大环境
│   ├── regime.json                   # 牛熊状态+板块统计
│   └── indices.json                  # 三大指数涨跌
│
├── 2-themes/                         # 概念题材（三级漏斗第二级，当前缺失）
│   ├── all_themes.json               # 全量概念板块TFS状态+得分
│   ├── hot_themes.json               # 热门题材TopN
│   └── theme_stock_map.json          # 题材→成分股映射
│
├── 3-sectors/                        # 行业板块（三级漏斗第一级）
│   ├── all_sectors.json              # 板块状态+龙头（数量动态，不硬编码90）
│   ├── focus.json                    # 焦点+观察区
│   └── sector_theme_map.json         # 板块→所属题材
│
├── 4-candidates/                     # 趋势筛选后的候选池
│   ├── etf_pool.json                 # state≥3 ETF + 趋势强度评分
│   ├── stock_pool.json               # state≥3 个股 + 趋势强度评分
│   └── scores.json                   # 全量评分排名
│
├── 5-recommendations/                # 最终推荐+推演
│   ├── top5_etfs.json                # Top5 + 6Widget完整数据
│   ├── top5_stocks.json              # Top5 + 6Widget完整数据
│   └── watchlist.json                # 特别关注
│
├── 6-display/                        # 可直接打开的展示层
│   ├── dashboard.html
│   └── sidebar_entry.json            # 侧边栏条目
│
└── summary.json                      # 当日摘要
```

## 四、pkl原始缓存 vs 日期目录

- `data/etf_stocks/` `data/massive_stocks/` — pkl原始缓存（全量历史，保留）
- `data/dates/{date}/` — 日期快照（新建，每日自包含）
- 两者共存：pkl是数据源，date目录是数据产品

## 五、改造计划

1. 全量数据下载完成后
2. 最近30天逐日建目录，跑完整流水线
3. 验证每天6层数据齐全
4. 旧散落文件逐步迁移后删除

## 六、禁止事项

1. ❌ 禁止日期目录缺少某一层
2. ❌ 禁止不同日期数据混放在同一文件
3. ❌ 禁止在日期目录外创建新的数据文件
4. ❌ 禁止硬编码板块/题材数量
