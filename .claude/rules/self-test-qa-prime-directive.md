---
name: self-test-qa-prime-directive
description: 最高优先级 — 数据和UI改动必须先自测再交付，用Playwright做像素级校验，严禁跳过
metadata:
  type: project
  priority: highest
---

# 交付前自测最高准则

## 一、核心原则

**任何涉及数据或UI的改动，必须先经过严格自测，确认与目标完全一致后才能交付。严禁不测试、不检查、不验证直接交付。**

本规则优先级为系统最高级，任何其他规则不得与之冲突。每次任务都必须执行。

## 二、强制流程（5步，不可跳过）

| 步骤 | 动作 | 说明 |
|------|------|------|
| 1 | **单元验证** | 改动后立即运行 Python 脚本验证数据正确性（如 widget-details 计数、名称对照、score 范围等） |
| 2 | **浏览器检查** | 使用 Playwright 启动无头浏览器，打开 `http://localhost:8765/index.html` |
| 3 | **像素级校验** | 截图与 `debug_done.png` 或桌面样本对比，检查：panel 颜色、布局、widget 展开状态、个股名称、表格内容 |
| 4 | **自动打开** | 执行 `open http://localhost:8765/index.html` 打开浏览器供用户肉眼确认 |
| 5 | **确认交付** | 以上全部通过后，才能输出最终结果 |

## 三、Playwright 检查项清单

每次 UI 改动后，必须用 Playwright 逐项检查：

```
□ 页面加载成功（HTTP 200）
□ 稳健推荐面板存在，边框 #4ade80
□ 强势追踪面板存在，边框 #06b6d4
□ 深度穿透面板存在，边框 #d29922
□ 焦点板块面板存在，边框 #42a5f5
□ 趋势个股面板存在，边框 #f472b6
□ widget-details 数量 ≥ 120
□ details 标签数量 ≥ 120
□ 所有 widget 可展开/收起
□ 个股名称显示为中文（非纯代码）
□ ETF 名称显示为中文
□ iframe 正确加载 dashboard 页面
□ 侧边栏日期导航正常
□ 无 JS 控制台错误
□ 无 404 请求
```

## 四、验证脚本模板

```python
# 必须做的快速验证
h = open('dashboard/trend_dashboard_{DATE}.html').read()
assert 'widget-details' in h, 'MISSING: widget-details'
assert h.count('<details ') >= 120, f'details too few: {h.count("<details ")}'
assert '深科技' in h or '平安银行' in h, 'Stock names missing'
```

## 五、红线

- ❌ 禁止不经 Playwright 检查直接说"已完成"
- ❌ 禁止只检查 Python 数据不检查浏览器渲染
- ❌ 禁止不自动打开 `open http://localhost:8765/index.html` 
- ❌ 禁止用 curl 代替浏览器检查
- ❌ 禁止跳过任何检查步骤
