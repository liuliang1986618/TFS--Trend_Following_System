"""每日JSON快照产出 — 趋势引擎全量输出。

设计文档§9.12 数据流:
  趋势引擎每日产出JSON → HTML Dashboard加载JSON渲染
  每个交易日的JSON快照存放于 dashboard/data/trend_snapshot_{date}.json

为什么需要每日快照？
→ 多赚钱：保存每日完整分析结果=可回溯任何一天的市场状态。
  回溯=发现规律=优化参数=持续提高赚钱效率。
→ 少亏钱：每日快照独立存储(不覆盖)，某天数据出错不影响其他天。
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from ..engine.state_machine import TrendState
from ..engine.conditions import ConditionResult
from ..engine.stage import StageClassifier, StageResult
from ..engine.key_points import KeyPointDetector, KeyPoint
from ..funnel.confidence import ConfidenceCalculator
from ..analysis.comparison import TrendComparison
from ..analysis.scenario import ScenarioEngine
from ..analysis.beta import BetaCalculator
from ..analysis.breadth import MarketBreadth


class SnapshotGenerator:
    """每日JSON快照生成器。

    输入所有层级的趋势分析结果 → 产出单一JSON文件。
    Dashboard只需加载一个JSON即可获得全部决策所需信息。

    为什么一次生成所有层级？
    → 多赚钱：Dashboard直接渲染无需计算，加载快=决策快=赚钱快。
    → 少亏钱：所有数据在同一文件内，不存在数据不一致的风险。
    """

    def __init__(self, output_dir: str = "dashboard/data"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self, date_str: str,
                 sector_results: Dict[str, TrendState],
                 theme_results: Dict[str, TrendState],
                 stock_results: Dict[str, TrendState],
                 etf_results: Dict[str, TrendState],
                 sector_names: Dict[str, str] = None,
                 theme_names: Dict[str, str] = None,
                 stock_names: Dict[str, str] = None,
                 etf_names: Dict[str, str] = None,
                 etf_types: Dict[str, str] = None,
                 previous_snapshot: dict = None,
                 positions: dict = None,
                 leader_results: Dict[str, list] = None,
                 beta_results: Dict[str, float] = None,
                 funnel_etfs: set = None,
                 direct_etfs: set = None,
                 ) -> dict:
        """生成完整每日快照。

        Args:
            date_str: 交易日日期，如 '2024-01-15'
            sector_results: 板块趋势结果 {bk_code: TrendState}
            theme_results: 题材趋势结果 {gn_code: TrendState}
            stock_results: 个股趋势结果 {stock_code: TrendState}
            etf_results: ETF趋势结果 {etf_code: TrendState}
            sector_names: 板块代码→名称映射
            theme_names: 题材代码→名称映射
            stock_names: 个股代码→名称映射
            etf_names: ETF代码→名称映射
            etf_types: ETF代码→类型映射
            previous_snapshot: 前一交易日的快照dict(用于对比和关键点检测)
            positions: 当前持仓dict
            leader_results: 领涨股结果 {code: [(symbol, score), ...]}
            beta_results: 板块beta值 {bk_code: beta}
            funnel_etfs: 漏斗路径命中的ETF代码集合
            direct_etfs: ETF直筛路径命中的代码集合

        → 多赚钱：一次生成所有层级的分析结果，Dashboard直接渲染无需计算。
        """
        overview = self._build_overview(sector_results, theme_results, stock_results, etf_results)

        # 生成各层级列表(先于key_actions, 因为overview需要key_actions_count)
        sectors = self._build_sector_list(sector_results, sector_names, beta_results)
        themes = self._build_theme_list(theme_results, theme_names, leader_results)
        stocks = self._build_stock_list(stock_results, stock_names, leader_results)
        etfs = self._build_etf_list(etf_results, etf_names, etf_types, funnel_etfs or set(), direct_etfs or set())
        key_actions = self._build_key_actions(stock_results, etf_results, previous_snapshot)

        overview["key_actions_count"] = len(key_actions)

        snapshot = {
            "meta": {
                "date": date_str,
                "generated_at": datetime.now().isoformat(),
                "version": "1.0",
            },
            "market_overview": overview,
            "sectors": sectors,
            "themes": themes,
            "stocks": stocks,
            "etfs": etfs,
            "key_actions": key_actions,
            "scenario_plans": self._build_scenarios(stock_results, stock_names),
            "watchlist": self._build_watchlist(stock_results, stock_names, previous_snapshot),
            "comparison": self._build_comparison(sector_results, previous_snapshot),
            "market_breadth": MarketBreadth.calculate(sector_results, stock_results, etf_results),
            "positions": positions or {},
        }

        self._save(snapshot, date_str)
        return snapshot

    # ── 概览 ──────────────────────────────────────────

    def _build_overview(self, sectors, themes, stocks, etfs):
        """构建市场概览卡片数据。

        为什么选这4个核心数字？
        → 多赚钱：上涨板块数=机会广度，趋势个股数=机会深度。
          活跃题材数=市场热度，趋势ETF数=可执行信号量。
          4个数字一眼判断今天是该积极进攻还是保守防守。
        """
        uptrend_sectors = sum(1 for t in sectors.values() if t.state in {3, 4, 5})
        active_themes = sum(1 for t in themes.values() if t.state in {3, 4})
        trend_stocks = sum(1 for t in stocks.values() if t.state in {3, 4, 5})
        trend_etfs = sum(1 for t in etfs.values() if t.state in {3, 4, 5})

        # 市场情绪判断
        if uptrend_sectors >= 15 and trend_stocks >= 100:
            mood = "乐观 — 机会充裕，可积极进攻"
        elif uptrend_sectors >= 8:
            mood = "中性 — 结构性机会，精选标的"
        else:
            mood = "谨慎 — 机会稀少，多看少动"

        return {
            "uptrend_sectors": uptrend_sectors,
            "active_themes": active_themes,
            "trend_stocks": trend_stocks,
            "trend_etfs": trend_etfs,
            "market_mood": mood,
            "key_actions_count": 0,  # 由generate更新
        }

    # ── 板块列表 ──────────────────────────────────────

    def _build_sector_list(self, results, names, betas):
        """构建板块详情列表。

        → 多赚钱：按得分排序，一眼看到最强的板块。
        → 少亏钱：beta值辅助判断进攻/防御属性。
        """
        sectors = []
        for code, ts in results.items():
            item = self._base_item(code, names.get(code, code) if names else code, "sector", ts)
            item["bk_code"] = code
            if betas and code in betas:
                item["beta"] = betas[code]
                item["beta_label"] = BetaCalculator.interpret(betas[code])
            item["external_link"] = f"https://q.10jqka.com.cn/stock/bk/{code}/"
            sectors.append(item)
        sectors.sort(key=lambda x: x["score"], reverse=True)
        return sectors

    # ── 题材列表 ──────────────────────────────────────

    def _build_theme_list(self, results, names, leaders):
        """构建题材详情列表。

        → 多赚钱：领涨股信息快速定位题材内最强势个股。
        """
        themes = []
        for code, ts in results.items():
            item = self._base_item(code, names.get(code, code) if names else code, "theme", ts)
            item["gn_code"] = code
            if leaders and code in leaders:
                item["leaders"] = [{"symbol": s, "score": sc} for s, sc in leaders[code][:3]]
            item["external_link"] = f"https://q.10jqka.com.cn/gn/detail/code/{code}/"
            themes.append(item)
        themes.sort(key=lambda x: x["score"], reverse=True)
        return themes

    # ── 个股列表 ──────────────────────────────────────

    def _build_stock_list(self, results, names, leaders):
        """构建个股详情列表。包含止损价。

        为什么每个标的都附带止损价？
        → 少亏钱：止损价=前低下方0.5%。破位即走，不犹豫。
          提前算好止损价=消除情绪干扰=机械化执行。
        """
        stocks = []
        for code, ts in results.items():
            item = self._base_item(code, names.get(code, code) if names else code, "stock", ts)
            item["external_link"] = f"https://stockpage.10jqka.com.cn/{code}/"
            # 止损价=前低下方0.5%
            if ts.prev_low:
                item["stop_loss"] = round(ts.prev_low["price"] * 0.995, 2)
            else:
                item["stop_loss"] = None
            # 突破/跌破标记
            item["broke_prev_high"] = ts.broke_prev_high
            item["broke_prev_low"] = ts.broke_prev_low
            stocks.append(item)
        stocks.sort(key=lambda x: x["score"], reverse=True)
        return stocks

    # ── ETF列表 ───────────────────────────────────────

    def _build_etf_list(self, results, names, types, funnel_etfs, direct_etfs):
        """构建ETF详情列表。附带置信度信息。

        为什么ETF需要置信度？
        → 少亏钱：低置信度信号应减小仓位。
          双路确认(漏斗+直筛)的ETF=最高置信度=可以标准仓位。
          单路命中=需谨慎=试探仓位。
        """
        etfs = []
        for code, ts in results.items():
            item = self._base_item(code, names.get(code, code) if names else code, "etf", ts)
            item["etf_type"] = types.get(code, "B") if types else "B"
            # 置信度 — 双路交叉验证
            conf = ConfidenceCalculator.calculate_etf(code, funnel_etfs, direct_etfs)
            item["confidence"] = conf["confidence"]
            item["confidence_source"] = conf["source"]
            item["position_multiplier"] = conf["position_multiplier"]
            item["external_link"] = f"https://stockpage.10jqka.com.cn/{code}/"
            etfs.append(item)
        etfs.sort(key=lambda x: x["score"], reverse=True)
        return etfs

    # ── 基础标的构建 ─────────────────────────────────

    def _base_item(self, code, name, item_type, ts):
        """构建标的的基础信息。每个字段都来自状态机输出。

        为什么每个字段都能解释"为什么是这个状态"？
        → 多赚钱+少亏钱：完整的条件详情+信号+pivots=清晰的决策链条。
          Dashboard可以完整展示"为什么买/卖/持有"，消除模糊性。
        """
        # 阶段分类 — 仅对上涨相关状态有意义
        stage_info = self._classify_stage(ts)

        return {
            "symbol": code,
            "name": name,
            "type": item_type,
            "state": ts.state,
            "state_label": ts.state_label,
            "stage": stage_info["stage"],
            "stage_label": stage_info["label"],
            "stage_reasons": stage_info["reasons"],
            "position_ratio": ts.position_ratio,
            "score": self._calc_score(ts),
            "conditions": {
                "structure": {
                    "pass": ts.conditions["structure"].pass_,
                    "detail": ts.conditions["structure"].detail,
                },
                "volume": {
                    "pass": ts.conditions["volume"].pass_,
                    "detail": ts.conditions["volume"].detail,
                },
                "persistence": {
                    "pass": ts.conditions["persistence"].pass_,
                    "detail": ts.conditions["persistence"].detail,
                },
            },
            "signals": {
                "above_ma20": ts.above_ma20,
                "volume_surge": ts.volume_surge,
                "volume_shrink": ts.volume_shrink,
                "consecutive_rise": ts.consecutive_rise,
                "consecutive_drop": ts.consecutive_drop,
            },
            "pivots": {
                "prev_high": {"date": str(ts.prev_high["date"]), "price": ts.prev_high["price"]} if ts.prev_high else None,
                "prev_low": {"date": str(ts.prev_low["date"]), "price": ts.prev_low["price"]} if ts.prev_low else None,
            },
        }

    def _classify_stage(self, ts):
        """从TrendState推断趋势阶段。

        为什么不在快照层面做完整阶段分类？
        → 快照只持有TrendState结果，没有原始日K数据。
          从状态和信号做简化推断已经足够Dashboard使用。
        """
        state = ts.state
        reasons = []

        if state == 3:
            return {"stage": "early", "label": "前期",
                    "reasons": ["状态3翻转确认中，处于趋势初期——盈亏比最佳位置"]}
        elif state == 4:
            # 判断是中期还是后期
            late_count = 0
            if ts.consecutive_drop:
                reasons.append("出现连续下跌——警惕趋势松动")
                late_count += 1
            if ts.volume_surge and not ts.broke_prev_high:
                reasons.append("放量但未创新高——可能滞涨")
                late_count += 1
            if late_count >= 2:
                return {"stage": "late", "label": "后期", "reasons": reasons}
            elif late_count == 1:
                return {"stage": "mid_late", "label": "中后期",
                        "reasons": reasons + ["状态4持续运行，个别信号需关注"]}
            else:
                return {"stage": "mid", "label": "中期",
                        "reasons": ["状态4健康运行，无异常信号——主升浪持股"]}
        elif state == 5:
            if ts.consecutive_drop and ts.volume_surge:
                return {"stage": "mid", "label": "中期(回调)",
                        "reasons": ["正常回调中，放量下跌需密切关注——等企稳信号"]}
            return {"stage": "mid", "label": "中期(回调)",
                    "reasons": ["正常回调，缩量整理——珍惜筹码, 等加仓机会"]}
        elif state == "3'":
            return {"stage": "defensive", "label": "防守",
                    "reasons": ["转跌确认——保护利润，等待方向明确"]}
        return {"stage": "", "label": "",
                "reasons": ["非上涨趋势状态，不适用阶段分类"]}

    def _calc_score(self, ts):
        """计算综合得分(0-100)，用于Dashboard排序。

        为什么用得分而不是仅按状态排序？
        → 多赚钱：同一状态内，三条件全过的比只过一个的更可靠。
          得分=状态基础分+条件加分，精细化排序=优先关注最强标的。
        """
        state_score = {4: 70, 5: 55, 3: 40, 2: 15, 1: 0, "3'": 10}
        base = state_score.get(ts.state, 0)
        if ts.conditions["structure"].pass_:
            base += 10
        if ts.conditions["volume"].pass_:
            base += 10
        if ts.conditions["persistence"].pass_:
            base += 10
        return min(base, 100)

    # ── 关键操作点 ───────────────────────────────────

    def _build_key_actions(self, stock_results, etf_results, prev_snapshot):
        """构建关键操作点列表。需要前一日数据做状态对比。

        为什么需要前一日快照数据？
        → 少亏钱：关键操作点(买点1/买点2/止损/防守等)都是状态转换触发。
          单看今天的数据无法判断"发生了什么变化"。
          对比前后两天的状态才能精准识别操作信号。
        """
        actions = []
        if not prev_snapshot:
            return actions

        # 个股操作点
        prev_stocks = {}
        for s in prev_snapshot.get("stocks", []):
            prev_stocks[s["symbol"]] = s

        for code, ts in stock_results.items():
            if code in prev_stocks:
                prev_state = prev_stocks[code]["state"]
                kp = KeyPointDetector.detect(prev_state, ts.state)
                if kp:
                    actions.append({
                        "symbol": code,
                        "name": prev_stocks[code].get("name", code),
                        "target_type": "stock",
                        "transition": kp.transition,
                        "action": kp.action,
                        "priority": kp.priority,
                        "position_action": kp.position_action,
                        "description": kp.description,
                        "prev_state": prev_state,
                        "current_state": ts.state,
                    })

        # ETF操作点
        prev_etfs = {}
        for s in prev_snapshot.get("etfs", []):
            prev_etfs[s["symbol"]] = s

        for code, ts in etf_results.items():
            if code in prev_etfs:
                prev_state = prev_etfs[code]["state"]
                kp = KeyPointDetector.detect(prev_state, ts.state)
                if kp:
                    actions.append({
                        "symbol": code,
                        "name": prev_etfs[code].get("name", code),
                        "target_type": "etf",
                        "transition": kp.transition,
                        "action": kp.action,
                        "priority": kp.priority,
                        "position_action": kp.position_action,
                        "description": kp.description,
                        "prev_state": prev_state,
                        "current_state": ts.state,
                    })

        # 按优先级排序: 🔴 > 🟠 > 🟢 > 🟡
        priority_order = {"🔴": 0, "🟠": 1, "🟢": 2, "🟡": 3}
        actions.sort(key=lambda x: priority_order.get(x["priority"], 99))
        return actions

    # ── 明日推演 ─────────────────────────────────────

    def _build_scenarios(self, stock_results, names):
        """为每个持仓标的生成明日推演。

        为什么生成3个概率场景而不是1个预测？
        → 少亏钱：预测唯一场景=赌博。推演3个场景=预案覆盖大概率到小概率。
          无论明天发生什么都在预案中=不慌不乱=按计划执行。
        → 多赚钱：场景B(中概率)往往藏着最佳操作时机(加仓/止盈)。
        """
        plans = []
        for code, ts in stock_results.items():
            # 只对处于有意义状态的标生成推演(排除状态1和2)
            if ts.state not in {3, 4, 5, "3'"}:
                continue
            scenarios = ScenarioEngine.generate(ts)
            plans.append({
                "symbol": code,
                "name": names.get(code, code) if names else code,
                "current_state": ts.state_label,
                "position": ts.position_ratio,
                "stop_loss": round(ts.prev_low["price"] * 0.995, 2) if ts.prev_low else None,
                "scenarios": [
                    {"label": s.label, "probability": s.probability,
                     "conditions": s.conditions, "action": s.action,
                     "next_state": s.next_state}
                    for s in scenarios
                ],
            })
        return plans

    # ── 观察列表 ─────────────────────────────────────

    def _build_watchlist(self, stock_results, stock_names, prev_snapshot):
        """构建观察列表：状态2(下跌反弹)和刚退出上涨状态的标的。

        为什么需要观察列表？
        → 多赚钱：状态2的标的是潜在买点1候选人。提早在观察列表里盯前高，
          一旦放量突破=立即执行买点1=抢在趋势启动前入场。
        → 少亏钱：刚退出上涨的标的=可能是假跌破=观察是否快速修复。
        """
        watchlist = []
        # 状态2标的(下跌反弹) — 潜在买点1候选人
        for code, ts in stock_results.items():
            if ts.state == 2:
                watchlist.append({
                    "symbol": code,
                    "name": stock_names.get(code, code) if stock_names else code,
                    "state": ts.state,
                    "state_label": ts.state_label,
                    "reason": "下跌反弹，盯前高——放量突破=买点1",
                    "prev_high": ts.prev_high["price"] if ts.prev_high else None,
                    "score": self._calc_score(ts),
                })

        # 刚退出上涨状态的标的(从昨日快照对比)
        if prev_snapshot:
            prev_stocks = {}
            for s in prev_snapshot.get("stocks", []):
                prev_stocks[s["symbol"]] = s

            for code, ts in stock_results.items():
                if code in prev_stocks:
                    prev_state = prev_stocks[code]["state"]
                    was_uptrend = prev_state in {3, 4, 5}
                    is_uptrend = ts.state in {3, 4, 5}
                    if was_uptrend and not is_uptrend:
                        watchlist.append({
                            "symbol": code,
                            "name": stock_names.get(code, code) if stock_names else code,
                            "state": ts.state,
                            "state_label": ts.state_label,
                            "reason": f"退出上涨(状态{prev_state}→{ts.state})，关注是否假跌破",
                            "prev_high": ts.prev_high["price"] if ts.prev_high else None,
                            "score": self._calc_score(ts),
                        })

        watchlist.sort(key=lambda x: x["score"], reverse=True)
        return watchlist

    # ── 趋势对比 ─────────────────────────────────────

    def _build_comparison(self, current, prev_snapshot):
        """趋势变化对比 — vs 昨日。

        为什么需要对比？
        → 多赚钱：新进入上涨=新机会，退出上涨=规避风险。
          趋势是动态过程，对比变化才能发现拐点。
        """
        if not prev_snapshot:
            return {"new_uptrend": [], "exited_uptrend": [],
                    "note": "首次运行，无前日对比数据 — 明日开始显示趋势变化"}

        # 从前日快照重建状态映射(仅用于对比)
        prev_sector_states = {}
        for s in prev_snapshot.get("sectors", []):
            prev_sector_states[s["symbol"]] = s["state"]

        uptrend_states = {3, 4, 5}
        new_uptrend = []
        exited_uptrend = []
        state_changed = []

        for code, ts in current.items():
            curr_state = ts.state
            prev_state = prev_sector_states.get(code)
            if prev_state is None:
                if curr_state in uptrend_states:
                    new_uptrend.append({
                        "code": code,
                        "prev_state": "NEW",
                        "curr_state": curr_state,
                        "change": "新增标的，进入上涨",
                    })
                continue

            prev_in = prev_state in uptrend_states
            curr_in = curr_state in uptrend_states

            if not prev_in and curr_in:
                new_uptrend.append({
                    "code": code,
                    "prev_state": prev_state,
                    "curr_state": curr_state,
                    "change": f"状态{prev_state}→{curr_state}，进入上涨",
                })
            elif prev_in and not curr_in:
                exited_uptrend.append({
                    "code": code,
                    "prev_state": prev_state,
                    "curr_state": curr_state,
                    "change": f"状态{prev_state}→{curr_state}，退出上涨",
                })
            elif prev_state != curr_state:
                state_changed.append({
                    "code": code,
                    "prev_state": prev_state,
                    "curr_state": curr_state,
                })

        return {
            "new_uptrend": new_uptrend,
            "exited_uptrend": exited_uptrend,
            "state_changed": state_changed,
            "note": "",
        }

    # ── 存储 ─────────────────────────────────────────

    def _save(self, snapshot, date_str):
        """保存快照到JSON文件。

        为什么用JSON而不是数据库？
        → 简单可靠：JSON可直接在浏览器中加载，无需服务器。
          每日一个文件=天然备份=数据损坏不影响其他天。
        """
        path = os.path.join(self.output_dir, f"trend_snapshot_{date_str}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
