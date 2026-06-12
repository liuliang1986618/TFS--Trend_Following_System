# 展示层最高准则

## 一、核心定理

**标准模板HTML文件是真理。Python只做 `str.replace` 替换数据值。零HTML生成。**

```
dashboard/data/standard_template.html   ← 671KB，全部CSS/HTML/JS的载体
scripts/render_action_panel.py          ← 只做 str.replace(旧数据, 新数据)
```

## 二、唯一正确做法

```python
# 1. 加载标准模板（671KB HTML文件）
template = open('dashboard/data/standard_template.html').read()

# 2. 找到旧数据，替换为新数据
template = template.replace('煤炭ETF', '科创机械ETF嘉实')
template = template.replace('(515220)', '(588850)')
template = template.replace('评分 74.0', '评分 84.0')
# ... 替换所有可变数据字段

# 3. 保存
open(f'dashboard/trend_dashboard_{date}.html', 'w').write(template)
```

**就这么简单。** 不要：定义CSS变量、拼接HTML标签、写f-string模板、调用任何HTML生成函数。

## 三、绝对禁止

1. ❌ `h += '<div style="...">'` — Python拼接HTML
2. ❌ `f'<span>{value}</span>'` — f-string生成标签
3. ❌ `render_card()` / `render_widget()` 等HTML生成函数
4. ❌ 在 build_final.py 或 build_nav_index.py 中添加任何面板代码
5. ❌ 复制参考CSS到Python代码中——CSS属于模板文件，不属于代码

## 四、为什么Python生成HTML必然失败

每次Python生成HTML，都会引入不可见的差异：
- 属性顺序不同（`style="color:red;font-size:12px"` vs `style="font-size:12px;color:red"`）
- 空格/换行不同
- 引号风格不同（`'` vs `"` vs `&quot;`）
- 数值精度不同（`74.0` vs `74` vs `74.00`）

**只有 `str.replace` 能保证100%一致，因为除了被替换的数据值，其他所有字节原封不动。**

## 五、标准模板文件

```
dashboard/data/standard_template.html   ← 671KB，永不修改
```

- 来源：用户确认过的正确展示效果（浏览器保存的完整HTML）
- 内容：包含完整的页面结构、CSS、JS、布局
- 维护：样式变更 = 替换这个文件为新版本
- 作用：渲染器加载它，替换数据值，输出当天页面

## 六、构建顺序（不可变）

```
1. build_final.py             → 产出基础仪表板
2. render_action_panel.py     → 加载模板 → str.replace数据 → 保存
3. build_funnel_cards.py      → 构建四级漏斗数据JSON
4. render_funnel_panel.py     → 渲染漏斗面板HTML → 注入页面
5. build_nav_index.py         → 侧边栏壳（必须最后！）
6. 验证                        → 8项检查
```

**注意：** `build_funnel_cards.py` 依赖 `data/etf_holdings.json` 和 `data/theme_holdings.json` 缓存，首次运行前需执行：
```bash
python3 scripts/build_etf_holdings_cache.py   # ETF持仓缓存(季度更新)
python3 scripts/build_theme_holdings_cache.py  # 题材成分股缓存(季度更新)
```

## 七、验证清单

```python
h = open(f'dashboard/trend_dashboard_{date}.html').read()
assert h.count('明日操作建议') == 1
assert '4ade80' in h
assert 'widget-details' in h
assert 'ETF操作' in h and '个股操作' in h
assert 'f0883e' in h
assert '四级漏斗' in h
assert '趋势最强题材' in h
```

## 八、历史错误全景

| # | 错误 | 根因 | 教训 |
|---|------|------|------|
| 1 | heredoc注入代码到build_final | 数据逻辑混入展示层 | 独立渲染脚本 |
| 2 | 双代码块共存 | 没检查旧代码残留 | 先grep确认 |
| 3 | 双面板输出 | 两套代码都往h写HTML | 单一代码源 |
| 4 | 删A误删B | 字符串匹配边界不准 | 独立文件 |
| 5 | f-string重新生成HTML | 以为结构一样就行 | 模板直接替换数据 |
| 6 | build_nav被覆盖 | build_final也写index.html | 构建顺序固化 |
| 7 | grep误报 | 大文件输出截断 | Python读取验证 |
| 8 | 改完不验证 | 没有自动化检查 | 每次构建后强制验证 |
| 9 | 手调CSS颜色字体 | 手工拼HTML不可能一致 | CSS属于模板文件 |
| 10 | 不听用户指令 | 自以为是绕圈 | 执行用户给定架构 |
| 11 | 重写render时又手写CSS | 从记忆写而非从模板复制 | 任何样式从模板提取 |
| 12 | 策略总纲颜色反复错 | Python代码里的CSS和模板不一致 | CSS只在模板文件里 |

| 13 | 页面无明日操作建议 | **漏跑 render_action_panel.py**，构建序列不完整 | 构建序列三步不可缺一，自动化脚本强制顺序执行 |
| 14 | render默认日期硬编码 | `sys.argv[1] else '2026-06-09'` 死日期 | 默认日期从 dashboard_data.json 读取 |
| 15 | ETF名称显示为代码 | ETF_NAME_MAP只157条 | akshare全量→etf_names.json(1503只) |
| 16 | 漏斗面板重复渲染 | inject不删旧面板 | 注入前去重，先删再插 |
| 17 | 题材ETF关键词不匹配 | "芯片概念"→无ETF | 同义词扩展(芯片≈半导体)+产品词提取 |
| 18 | 交付不验证 | 说"已打开"但未Playwright确认 | 改后必须Playwright验证 |
| 19 | 浏览器缓存旧页面 | `http.server` 无Cache-Control头 | **必须用no-cache服务，禁用系统默认http.server** |

**十九条错误。最新四条根因：注入去重+关键词匹配+交付验证缺位+浏览器缓存。**
**核心教训：`python3 -m http.server` 不设缓存头，浏览器无限缓存旧页面，用户永远看到旧版本。Playwright正确但用户看到错误。根源在于HTTP服务层，不是代码层。**
