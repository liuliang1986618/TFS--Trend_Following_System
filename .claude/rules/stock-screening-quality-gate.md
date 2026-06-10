---
name: stock-screening-quality-gate
description: 标的筛选质量门禁 — 任何进入操作建议面板的标的必须通过多维趋势审查，涵盖过滤规则、数据来源、执行流程
metadata:
  type: project
---

# 标的筛选质量门禁

## 一、核心原则（不可违反）

1. **任何进入操作建议面板的标的，无论数据来源（pipeline实时评分 or 默认回退列表），都必须经过同一套筛选逻辑**
2. **筛选逻辑是代码的一部分，不是一个"建议"。不允许跳过、注释掉、或用空列表绕过**
3. **新增日期、新增标的、修改筛选逻辑 — 三者都必须跑全量验证**
4. **不允许偷懒：不创建空actions JSON绕过pipeline、不复制HTML文件改名、不跳过build_nav_index.py**
5. **ETF推荐必须行业分散** — 同一产品品类只取最强一只，禁止5只中4只同品类（如4/5都是半导体）

## 二、标的进入面板的完整流程

```
数据来源（二选一）
  │
  ├─ pipeline 实时评分 → actions_{date}.json (etf_top5/stock_top5)
  │   包含：code, name, score, action, position_pct, state, link
  │
  └─ 默认回退列表 → _DEFAULT_ETFS / _DEFAULT_STOCKS
      包含：code, name, link（无 score/action/state，由 _build_card 计算）
      注意：默认列表是"候选池"，不是"通过名单"。仍须经筛选。
  │
  ▼
_build_card() → 加载价格数据 → 计算指标 → 计算state → 筛选决策树
  │
  ├─ ✅ 通过 → 生成完整卡片（6 Widget）
  └─ ❌ 过滤 → return None（不出现在 etf_cards/stock_cards 中）
  │
  ▼
render_card() → 渲染 HTML（只有通过筛选的卡片才会渲染）
```

## 三、筛选决策树

**操作建议面板只推荐上升趋势标的。下跌/震荡偏弱的标的不具备推荐价值。**

```
标的进入筛选
  │
  ├─ 数据不足（< 60 天价格数据）
  │   → ❌ 跳过
  │
  ├─ state == 1 (下跌趋势)
  │   → ❌ 排除。不推荐下跌趋势中的标的
  │
  ├─ state == 2 (弱反弹/偏弱震荡)
  │   → ❌ 排除。趋势不够强，不建议操作
  │
  ├─ state == 3 (偏强震荡)
  │   ├─ pct_20d < -3%
  │   │   → ❌ 排除。中期动量为负，震荡偏弱
  │   └─ pct_20d >= -3%
  │       → ✅ 保留（评分 60-75）
  │
  ├─ state == 4 (上升趋势)
  │   → ✅ 保留（评分 80-100）
  │
  └─ 候选池来源
      ├─ pipeline 实时评分 → actions JSON → etf_top5/stock_top5
      └─ 空则动态扫描全量池 → _scan_best_etfs / _scan_best_stocks
```

## 四、趋势强度评分（0-100）

所有通过筛选的标的统一评分，按分数降序展示：

| 维度 | 计分规则 |
|------|---------|
| 趋势基础 | state×22（state=4→88, state=3→66） |
| 20日动量 | pct_20d×0.8，最多+15 |
| 均线多头 | ma_bullish → +8 |
| 中期多头 | ma_mid_bullish → +4 |
| 温和放量 | vol_ratio 1.0~2.0 → +3 |
| 短期回调 | pct_5d < -3% → 按比例扣分 |
| 总分 | 0-100，越高越好 |

## 四、判定字段速查

| 字段 | 含义 | 常见误用 |
|------|------|---------|
| `state` | TFS状态(1-4) | 不可仅凭state判定，需组合检查 |
| `ma_death_cross` | **今日**刚发生死叉 | ❌ 单独使用 → 漏掉3天前已死叉的情况 |
| `ma5_below_ma10` | MA5在MA10下方（持续） | ✅ 判断死叉的主要依据 |
| `price_below_ma5` | 收盘价 < MA5 | 短期趋势走弱信号 |
| `pct_5d` | 近5日涨跌幅 | 捕捉急跌，不可只看20日 |
| `pct_20d` | 近20日涨跌幅 | 中期趋势，不可只看5日 |

### ⚠️ 死叉检测铁律

```
ma_death_cross = 仅今日发生   ← 点事件，会漏
ma5_below_ma10 = 持续状态     ← 必须用这个判断
```

死叉可能3天前就发生了。必须同时检查两个字段，以 `ma5_below_ma10` 为主。

## 五、历史错误全景清单（共17条）

### A. 硬编码 & 数据来源错误

| # | 错误 | 具体表现 | 根因 | 教训 |
|---|------|---------|------|------|
| 1 | 硬编码默认ETF列表 | 5只新能源ETF永远不变 | 偷懒，没让列表随市场变化 | 禁止硬编码候选池 |
| 2 | 默认列表不经筛选 | 伟隆股份趋势破了照样进面板 | 静态列表绕过 `_build_card` 的质量筛选 | 任何来源的标的都走同一套筛选 |
| 3 | 新增日期用空actions JSON绕过pipeline | 手动创建空JSON | pipeline超时就偷懒 | 不允许手动创建空JSON |
| 4 | actions JSON空时无后备数据 | 130/131天面板空白 | 默认列表是后来才加的 | 任何情况下都不能面板空白 |
| 15 | 5只ETF全同行业且全下跌趋势 | 煤炭/通信/机器人被埋没 | 硬编码列表不考虑行业分散和趋势质量 | 必须从全量池动态择优，不能静态指定 |
| 16 | 推荐下跌趋势标的进入操作建议 | 下跌ETF出现在推荐面板 | state=1被设为"保留展示" | **推荐面板只推荐上升趋势** |
| 17 | 标的无评分、无排序 | 不知道哪个最好最差 | 没设计趋势强度评分系统 | 必须有评分→排序→展示分数 |

### B. 筛选逻辑错误

| # | 错误 | 具体表现 | 根因 | 教训 |
|---|------|---------|------|------|
| 5 | 只用 `ma_death_cross` 判断死叉 | 死叉3天后仍检测不到 | 把点事件当持续状态用 | 持续状态 > 点事件 |
| 6 | 只看`pct_20d`忽略`pct_5d` | 5天跌10%没被过滤 | 没想到急跌场景 | 多时间框架必须都查 |
| 7 | state=1直接`return None`（第一个版本） | 所有ETF被过滤 | 第一次修复过于激进 | 改了要验证全量 |
| 8 | state=1设为"保留展示"（第二个版本） | 下跌趋势被推荐 | 矫枉过正，推荐=只推好的 | 操作建议不是市场扫描，是推荐 |

### C. 流程 & 验证错误

| # | 错误 | 具体表现 | 根因 | 教训 |
|---|------|---------|------|------|
| 9 | 改完筛选只测一只标的 | ETF全灭没发现 | 偷懒 | 改筛选→全量验证→修复→再跑 |
| 10 | 过滤逻辑写了但没应用 | 硬编码列表绕过了 `_build_card` | 数据流没走通 | 跟踪数据流从入口到渲染 |
| 11 | 改了enhanced_actions.py没重新生成HTML | 代码改了页面没变 | 忘了依赖链 | 改数据→重跑生成→验证HTML |
| 12 | 复制HTML文件改名代替生成 | 侧边栏丢失、日期错乱 | 偷懒走捷径 | 必须走完整生成流程 |
| 13 | 写了规则但新会话不遵循 | 规则没自动加载 | 放错目录 | 规则必须在 `.claude/rules/` |
| 14 | 多次修同一个问题，每次引入新问题 | 侧边栏修了10次才稳定 | 只看眼前不看全局 | 修复前画数据流，修后跑完整验证 |
| 18 | ETF强势追踪4/5同品类 | 科创半导体/半导体设备/科创半导体设备未做行业分散 | 只看评分排名不管品类集中度 | ETF推荐必须品类去重，同品类只取最强一只 |

## 六、改动后强制验证（必须执行）

任何涉及 `enhanced_actions.py`、筛选逻辑、默认列表、或新增日期的改动后，**必须**执行：

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from src.enhanced_actions import EnhancedActionGenerator

gen = EnhancedActionGenerator()
etfs = ['515030','515700','515950','516090','516160']
stocks = ['002258','002527','002636','002871','003043']

print('=== 筛选结果 ===')
for code in etfs + stocks:
    is_etf = code.startswith('51')
    c = gen._build_card({'code':code,'name':code}, '2026-06-08', is_etf=is_etf)
    if c:
        st = c['state']
        d = c['trend_context']['direction']
        pos = c['trend_context']['today_position']
        print(f'  ✅ {code} state={st} {d} | {pos}')
    else:
        print(f'  ❌ {code} FILTERED')

# 质量门禁
etf_in = sum(1 for c in etfs if gen._build_card({'code':c,'name':c}, '2026-06-08', is_etf=True))
stock_in = sum(1 for c in stocks if gen._build_card({'code':c,'name':c}, '2026-06-08', is_etf=False))
assert etf_in >= 1, f'FAIL: 所有ETF被过滤 ({etf_in}/5)'
assert stock_in >= 1, f'FAIL: 所有个股被过滤 ({stock_in}/5)'
assert etf_in + stock_in >= 5, f'FAIL: 总量太少 ({etf_in+stock_in}/10)'

# 每个被过滤的标的必须有明确的过滤原因
for code in etfs + stocks:
    is_etf = code.startswith('51')
    c = gen._build_card({'code':code,'name':code}, '2026-06-08', is_etf=is_etf)
    if not c:
        # 验证：被过滤的标的确实满足过滤条件
        data = gen._load_price_data(code, is_etf)
        sliced = gen._slice_to_date(data, '2026-06-08')
        close = sliced['close'].astype(float)
        ind = gen._calc_indicators(close, sliced['volume'].astype(float),
                                    sliced.get('high',close).astype(float),
                                    sliced.get('low',close).astype(float))
        state = gen._determine_state(close)
        assert state == 2, f'{code} filtered but state={state}, should not be filtered!'
        assert ind.get('ma5_below_ma10') or ind.get('pct_5d',0) < -8, \
               f'{code} filtered but no valid reason (ma5_below_ma10={ind.get(\"ma5_below_ma10\")}, pct_5d={ind.get(\"pct_5d\",0)})'

print('✅ 全部门禁通过: ETF {}/{}, 个股 {}/{}'.format(etf_in, len(etfs), stock_in, len(stocks)))
"
```

## 七、绝对禁止（红线）

0. ❌ ST/退市股票进入系统 — 涨跌幅5%、退市风险高，趋势跟随不做这类标的。下载时直接过滤
1. ❌ 不经过筛选决策树直接将标的渲染到页面
2. ❌ 使用硬编码静态列表作为候选池 — 必须从全量池动态择优
3. ❌ 将 state<3 的标的放入操作建议面板（推荐=只推上升趋势）
4. ❌ 标的无评分直接展示（必须有趋势强度评分+排序）
5. ❌ 手动创建空的 `actions_{date}.json` 来绕过pipeline
6. ❌ 复制HTML文件改名代替 `build_final.py` 生成
7. ❌ 只用 `ma_death_cross` 不用 `ma5_below_ma10`
8. ❌ 只检查一个时间周期的涨跌幅
9. ❌ 改动筛选逻辑后不跑全量验证
10. ❌ 改动数据模块后不重新生成HTML
11. ❌ 更新任何数据文件后不跑对应的生成脚本
12. ❌ 在错误的目录存规则文件（必须在 `.claude/rules/`）
