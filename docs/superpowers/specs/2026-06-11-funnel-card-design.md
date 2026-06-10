# 四级漏斗穿透卡片 — 设计文档

## 目标

新增独立面板，展示Top3趋势最强板块的四级漏斗穿透：
板块 → 最佳ETF + 龙头个股 → 趋势最强题材 → 题材ETF + 题材龙头

## 面板位置

稳健/强势面板下方，焦点板块上方。

## 数据架构

### 新增模块

| 模块 | 输入 | 输出 | 职责 |
|------|------|------|------|
| `scripts/build_theme_holdings_cache.py` | akshare API | `data/theme_holdings.json` | 拉取题材成分股缓存 |
| `scripts/build_funnel_cards.py` | dashboard_data + enhanced_actions + 两个holdings缓存 | `dashboard/data/funnel_cards_{date}.json` | 构建漏斗数据 |
| `scripts/render_funnel_panel.py` | funnel_cards JSON | `trend_dashboard_{date}.html` | 渲染HTML面板 |

### 构建序列

```
build_final → render_action_panel → build_funnel_cards → render_funnel_panel → build_nav_index
```

### 数据缓存

| 文件 | 结构 | 更新频率 |
|------|------|---------|
| `data/etf_holdings.json` | `{etf_code: [{code, name}]}` | 季度 |
| `data/theme_holdings.json` | `{theme_code: [{code, name}]}` | 季度 |

## 漏斗卡片结构

```
┌─ 🔥 板块名 (state score) ─────────────────────┐
│ 📊 最佳ETF: xxx(分)    [可点击]                 │
│ 🏆 板块龙头: xxx xxx xxx                       │
│ ─────────────────────────────────              │
│ 🔗 趋势最强题材 (Top3, 按评分降序):               │
│   ├ 题材A (85分)                                │
│   │  📊 xxxETF(分) | 🏆 龙头: xxx xxx          │
│   ├ 题材B (78分)                                │
│   │  📊 xxxETF(分) | 🏆 龙头: xxx xxx          │
│   └ 题材C (72分)                                │
│      📊 无对应ETF | 🏆 龙头: xxx xxx            │
└────────────────────────────────────────────────┘
```

展示Top3板块，每板块展示Top3趋势最强题材。

## 数据处理逻辑

### build_funnel_cards.py

1. 从dashboard_data.json取sectors，按score降序取Top3（仅state≥3）
2. 每个板块：
   a. 匹配最佳ETF（关键词匹配，从enhanced_actions ETF池取最高分）
   b. 取板块龙头（sector.leaders Top3）
   c. 找关联题材：关键词匹配 theme_list + dashboard_data themes，按score降序取Top3
   d. 每个题材：
      - 匹配最佳ETF（同一套关键词匹配）
      - 从theme_holdings取成分股，跑_build_card，按score降序取Top3龙头

### 题材→ETF匹配

复用 `_etf_category_key` 关键词映射表，和板块→ETF同一套逻辑。

### 题材龙头计算

复用 `EnhancedActionGenerator._get_etf_trend_leaders()` 的等价逻辑。

## 渲染

`render_funnel_panel.py` 纯新写HTML拼接：
- 面板标题：`🔽 四级漏斗穿透 — Top3强势板块`
- 卡片样式参照现有焦点板块卡片CSS值
- 每张卡片：板块标题行 → ETF+龙头行 → 分隔线 → 题材下钻行
- ETF名称和龙头名均为可点击东方财富链接

## 验证

```bash
# 1. 拉取题材成分股缓存
python3 scripts/build_theme_holdings_cache.py

# 2. 构建漏斗数据
python3 scripts/build_funnel_cards.py 2026-06-11

# 3. 渲染面板
python3 scripts/render_funnel_panel.py 2026-06-11

# 4. 侧边栏
python3 scripts/build_nav_index.py

# 5. 页面断言
python3 -c "
h=open('dashboard/trend_dashboard_2026-06-11.html').read()
assert '四级漏斗' in h
assert '趋势最强题材' in h
print('✅ 漏斗面板通过')
"
```
