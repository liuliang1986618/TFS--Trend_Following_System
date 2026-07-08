"""Stock, ETF, sector, and theme funnel orchestration for TFS v2.

提供漏斗式扫描：板块 → 最佳ETF → 板块龙头 → 题材穿透。
输出 Top6 板块卡片，每板块含 ABC 三条件、最佳ETF、龙头。
"""

from __future__ import annotations

from typing import Any

# 板块名 → ETF 品类关键词（迁移自 v1 build_funnel_cards.CATEGORY_ETF_MAP）
CATEGORY_ETF_MAP: dict[str, list[str]] = {
    '半导体': ['半导体', '芯片', '元件', '其他电子', '消费电子', '光学光电子', '电子化学品'],
    '通信设备': ['通信', '5G'],
    '通信': ['通信', '5G'], '消费电子': ['消费电子', '半导体', '元件'],
    '元件': ['半导体', '芯片', '电子', '光学光电子', '其他电子', '电子化学品'],
    '其他电子': ['芯片', '5G', '元件', '半导体', '消费电子', '光学光电子'],
    '电子化学品': ['电子', '化学', '半导体', '元件'],
    '机器人': ['机器人'], '白色家电': ['消费电子'],
    '电机': ['机器人'], '军工': ['军工'],
    '医药': ['医药', '医疗'], '银行': ['银行'], '证券': ['证券'],
    '汽车': ['新能源车'], '电力': ['电力'], '煤炭': ['煤炭'],
    '传媒': ['传媒'], '食品饮料': ['食品饮料', '消费'],
    '白酒': ['白酒', '酒'],
    '零售': ['零售', '电商', '消费'],
    '光学光电子': ['光学', '光电子', 'LED', '半导体', '元件'],
    '非金属材料': ['非金属', '材料', '化工', '建材'],
    '金属新材料': ['金属', '新材料', '有色', '稀土', '材料'],
    '小金属': ['小金属', '稀有', '稀土', '钨', '有色', '金属'],
    '工业金属': ['工业金属', '有色', '金属', '铜', '铝'],
    '自动化设备': ['自动化', '机器人', '智能', '设备'],
    '通用设备': ['通用设备', '设备', '机械'],
    '军工电子': ['军工', '电子', '国防'],
    '能源金属': ['能源金属', '锂', '钴', '镍', '有色'],
    '塑料制品': ['塑料', '化工', '材料'],
}

# 同义词扩展（芯片≈半导体）
KW_SYNONYMS: dict[str, list[str]] = {
    '芯片': ['芯片', '半导体'], '半导体': ['半导体', '芯片'],
    '5G': ['5G', '通信'], '通信': ['通信', '5G'],
    '光伏': ['光伏', '新能源'], '锂电池': ['锂电池', '新能源'],
}

ETF_PRODUCT_KW = ['半导体', '芯片', '通信', '5G', '消费电子', '机器人',
                  '新能源', '光伏', '锂电池', '军工', '医药', '银行', '证券',
                  '煤炭', '电力', '传媒', '食品饮料', '白酒', '家电', '汽车']


def match_best_etf(name: str, etf_pool: list[dict]) -> dict | None:
    """按板块名关键词匹配池中最高分 ETF（迁移自 v1 build_funnel_cards.match_best_etf）。"""
    keywords = CATEGORY_ETF_MAP.get(name, [])
    if not keywords:
        for kw in ETF_PRODUCT_KW:
            if kw in name:
                keywords.extend(KW_SYNONYMS.get(kw, [kw]))
        if not keywords:
            keywords = [name]
    best = None
    for e in etf_pool:
        ename = e.get('name', '')
        for kw in keywords:
            if kw in ename:
                if best is None or e.get('score', 0) > best.get('score', 0):
                    best = e
                break
    return best


class FunnelRunner:
    """漏斗扫描编排：板块分组 → Top6 → ABC + 最佳ETF + 龙头。"""

    def __init__(self, engine=None, data_layer=None):
        self.engine = engine
        self.data_layer = data_layer or (engine.data_layer if engine else None)

    def scan_stock_funnel(self, date: str | None = None, max_candidates: int | None = 50, top_sectors: int = 6) -> dict:
        """扫描全市场个股，按板块分组，每板块含 ABC/最佳ETF/龙头。funnel_cards 含全量板块（不限 Top6）。"""
        if self.engine is None:
            raise ValueError("FunnelRunner requires a TrendEngine")

        stocks = self.engine.scan_stock_full(date=date, max_candidates=max_candidates)
        relation_lookup = self._relation_entity_lookup()
        sector_names = relation_lookup.get("sectors", {})
        theme_names = relation_lookup.get("themes", {})

        # 板块分组（携带 signal 对象供龙头构造）
        sector_groups = self._group_by_relation_with_signals(stocks, "sectors", sector_names)

        # ETF 池（用于最佳ETF匹配）
        etf_pool = self._build_etf_pool(date)

        # 为所有板块补 ABC + 最佳ETF + 龙头（不限 Top6，builder 自己取 Top6 和 state∈{3,4}）
        funnel_cards = []
        for group in sector_groups:
            card = self._build_sector_card(group, etf_pool, theme_names)
            if card:
                funnel_cards.append(card)

        return {
            "relation_version": self._relation_version(),
            "sectors": [{"code": g["code"], "name": g["name"], "candidate_count": g["candidate_count"], "top_score": g["top_score"], "candidates": [s.code for s in g["candidates"]]} for g in sector_groups],
            "themes": self._group_by_relation(stocks, "themes", theme_names),
            "stocks": stocks,
            "funnel_cards": funnel_cards,
        }

    def scan_etf_direct(self, date: str | None = None, max_candidates: int | None = 50):
        """ETF 直筛（委托 engine）。"""
        if self.engine is None:
            raise ValueError("FunnelRunner requires a TrendEngine")
        return self.engine.scan_etf_direct(date=date, max_candidates=max_candidates)

    # ── 内部方法 ──────────────────────────────────────────────

    def _build_sector_card(self, group: dict, etf_pool: list[dict], theme_names: dict) -> dict | None:
        sector_code = group.get("code", "")
        sector_name = group.get("name", sector_code)
        candidate_signals = group.get("candidates", [])
        if not candidate_signals:
            return None

        # ABC 三条件：从板块 parquet 重新 classify（板块级 ABC，符合 v1 语义）
        abc_conditions = self._sector_abc(sector_code)

        # 最佳 ETF
        best_etf = match_best_etf(sector_name, etf_pool)

        # 板块龙头 top3（按 score 降序，带 name/score/state，门槛 state∈{3,4,5} 且 score≥60）
        candidate_signals_filtered = [s for s in candidate_signals if s.state in (3, 4, 5) and s.score >= 60]
        if not candidate_signals_filtered:
            candidate_signals_filtered = list(candidate_signals)
        sorted_signals = sorted(candidate_signals_filtered, key=lambda s: s.score, reverse=True)
        leaders = [{"code": s.code, "name": s.name, "score": s.score, "state": s.state, "state_label": s.state_label} for s in sorted_signals[:3]]

        # 5d 状态条 + sparkline（板块级历史）
        recent_states = []
        recent_scores = []
        if self.data_layer is not None and hasattr(self.data_layer, "history"):
            recent_states = self.data_layer.history.get_recent_states(sector_code, 5)
            recent_scores = self.data_layer.history.get_recent_scores(sector_code, 5)

        # 板块统计
        sector_stats = {}
        if self.data_layer is not None and hasattr(self.data_layer, "history"):
            sector_stats = self.data_layer.history.get_sector_stats(sector_code)

        return {
            "code": sector_code,
            "name": sector_name,
            "candidate_count": group.get("candidate_count", 0),
            "top_score": group.get("top_score", 0.0),
            "abc": abc_conditions,
            "best_etf": best_etf,
            "leaders": leaders,
            "recent_states": recent_states,
            "recent_scores": recent_scores,
            "sector_stats": sector_stats,
        }

    def _sector_abc(self, sector_code: str) -> dict:
        """从板块 parquet 跑 classifier 算 ABC 三条件。"""
        if self.data_layer is None:
            return {}
        try:
            from .classifier import TrendClassifier
            from .indicators import calculate_indicators
            from .params import StrategyParams
            daily_df = self.data_layer.load_daily("sector", sector_code)
            if len(daily_df) < 60:
                return {}
            params = self.engine.params if self.engine else StrategyParams()
            indicators = calculate_indicators(daily_df, params)
            classification = TrendClassifier().classify(daily_df, indicators)
            conditions = classification.get("conditions", {}) or {}
            state = classification.get("state")
            pct_20d = indicators.get("pct_20d", 0)
            vol_ratio = indicators.get("vol_ratio", 1.0)

            # ABC 文本构造（兼容 ConditionResult dataclass 和 dict 两种格式）
            def _cond_pass(key: str) -> bool:
                c = conditions.get(key)
                if c is None:
                    return False
                # ConditionResult dataclass: .pass_ 属性
                if hasattr(c, "pass_"):
                    return bool(getattr(c, "pass_", False))
                # dict 格式: .get("pass")
                if isinstance(c, dict):
                    return bool(c.get("pass", False))
                return bool(c)

            def _cond_detail(key: str) -> str:
                c = conditions.get(key)
                if c is None:
                    return ""
                if hasattr(c, "detail"):
                    return str(getattr(c, "detail", "") or "")
                if isinstance(c, dict):
                    return str(c.get("detail", "") or "")
                return ""

            structure_pass = _cond_pass("structure")
            volume_detail = _cond_detail("volume")
            persistence_pass = _cond_pass("persistence")
            volume_pass = _cond_pass("volume")

            if not volume_detail:
                if vol_ratio > 1.5:
                    volume_detail = f"放量（量比 {vol_ratio:.2f}）"
                elif vol_ratio < 0.8:
                    volume_detail = f"缩量（量比 {vol_ratio:.2f}）"
                else:
                    volume_detail = f"量能平稳（量比 {vol_ratio:.2f}）"

            return {
                "structure": f"{'✅' if structure_pass else '⏳'} 结构 {'通过' if structure_pass else '待确认'}，20日 {pct_20d:+.1f}%",
                "volume": f"{'✅' if volume_pass else '📊'} {volume_detail}",
                "persistence": f"{'✅' if persistence_pass else '⏳'} 持续性 {'通过' if persistence_pass else '待确认'}",
                "state": state,
                "pct_20d": pct_20d,
                "vol_ratio": vol_ratio,
                "conditions_raw": conditions,
            }
        except Exception:
            return {}

    def _group_by_relation_with_signals(self, signals: list, relation_key: str, names: dict) -> list[dict]:
        """按板块/题材分组候选，保留 signal 对象供龙头构造。"""
        groups: dict[str, dict] = {}
        for signal in signals:
            rels = getattr(signal, "relations", {}) or {}
            for code in rels.get(relation_key, []):
                group = groups.setdefault(code, {
                    "code": code,
                    "name": names.get(code, code),
                    "candidate_count": 0,
                    "top_score": 0.0,
                    "candidates": [],
                })
                group["candidate_count"] += 1
                group["top_score"] = max(group["top_score"], signal.score)
                group["candidates"].append(signal)
        return sorted(groups.values(), key=lambda x: (x["candidate_count"], x["top_score"], x["code"]), reverse=True)

    def _build_etf_pool(self, date: str | None = None) -> list[dict]:
        """构建 ETF 池用于最佳ETF匹配（取 state≥3 的 ETF）。"""
        if self.engine is None:
            return []
        try:
            etfs = self.engine.scan_etf_direct(date=date, max_candidates=50)
        except Exception:
            return []
        pool = []
        for sig in etfs:
            if sig.state not in (3, 4, 5):
                continue
            code = sig.code
            link = f"https://quote.eastmoney.com/sh{code}.html" if code.startswith("5") else f"https://quote.eastmoney.com/sz{code}.html"
            pool.append({
                "code": code,
                "name": sig.name,
                "score": sig.score,
                "state": sig.state,
                "link": link,
            })
        return pool

    def _group_by_relation(self, signals: list, relation_key: str, names: dict) -> list[dict]:
        """按板块/题材分组候选。"""
        groups: dict[str, dict] = {}
        for signal in signals:
            rels = getattr(signal, "relations", {}) or {}
            for code in rels.get(relation_key, []):
                group = groups.setdefault(code, {
                    "code": code,
                    "name": names.get(code, code),
                    "candidate_count": 0,
                    "top_score": 0.0,
                    "candidates": [],
                })
                group["candidate_count"] += 1
                group["top_score"] = max(group["top_score"], signal.score)
                group["candidates"].append(signal.code)
        return sorted(groups.values(), key=lambda x: (x["candidate_count"], x["top_score"], x["code"]), reverse=True)

    def _relation_entity_lookup(self) -> dict:
        if self.data_layer is None or not hasattr(self.data_layer, "get_relation_names"):
            return {"sectors": {}, "themes": {}}
        return self.data_layer.get_relation_names()

    def _relation_version(self) -> str | None:
        if self.data_layer and hasattr(self.data_layer, "get_relation_version"):
            return self.data_layer.get_relation_version()
        return None


__all__ = ["FunnelRunner", "match_best_etf", "CATEGORY_ETF_MAP"]
