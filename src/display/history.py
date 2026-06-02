"""趋势状态历史追踪器 — 从快照JSON或parquet原始数据中提取板块/个股状态历史。

用途:
  - Phase A: Dashboard 5-10天状态轨迹
  - Phase C/D: 全量822天状态历史用于推演回测

为什么需要缓存？避免73,890次重复classify()。预计算一次→所有后续查询O(1)→Dashboard秒开。
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
import os
from pathlib import Path


@dataclass
class StateRecord:
    """单日状态记录。"""
    date: str
    state: int  # 1,2,3,4,5 或 "3p"(代表3')
    state_label: str
    score: int
    position_ratio: float
    conditions: Dict[str, bool]


class HistoryTracker:
    """趋势状态历史追踪器。

    数据源：快照JSON（优先，快速）— 从 dashboard/data/trend_snapshot_*.json 读取。
    """

    def __init__(self, data_dir: str = "dashboard/data"):
        self.data_dir = Path(data_dir)
        self._cache: Dict[str, List[StateRecord]] = {}

    def load_from_snapshots(self, symbol_list: Optional[List[str]] = None) -> Dict[str, List[StateRecord]]:
        """从所有快照JSON文件中提取状态历史。

        Returns:
            {symbol: [StateRecord...]} 按日期排序
        """
        import glob

        pattern = str(self.data_dir / "trend_snapshot_*.json")
        snapshot_files = sorted(glob.glob(pattern))

        if not snapshot_files:
            return {}

        records: Dict[str, List[StateRecord]] = {}

        for fpath in snapshot_files:
            fname = os.path.basename(fpath)
            date_str = fname.replace("trend_snapshot_", "").replace(".json", "")

            try:
                with open(fpath) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                continue

            sectors = data.get("sectors", [])
            for s in sectors:
                code = s.get("code", s.get("symbol", s.get("bk_code", "")))
                if not code:
                    continue
                if symbol_list and code not in symbol_list:
                    continue

                conds = s.get("conditions", {})
                rec = StateRecord(
                    date=date_str,
                    state=self._normalize_state(s.get("state", 1)),
                    state_label=s.get("state_label", "未知"),
                    score=s.get("score", 0),
                    position_ratio=s.get("position_ratio", s.get("position", 0.0)),
                    conditions={
                        "structure": conds.get("structure", {}).get("pass", False) if isinstance(conds.get("structure"), dict) else bool(conds.get("structure", False)),
                        "volume": conds.get("volume", {}).get("pass", False) if isinstance(conds.get("volume"), dict) else bool(conds.get("volume", False)),
                        "persistence": conds.get("persistence", {}).get("pass", False) if isinstance(conds.get("persistence"), dict) else bool(conds.get("persistence", False)),
                    },
                )
                records.setdefault(code, []).append(rec)

        for code in records:
            records[code].sort(key=lambda r: r.date)

        self._cache.update(records)
        return records

    def get_recent_states(self, symbol: str, days: int = 10) -> List[StateRecord]:
        """获取某个标的最近N天的状态记录。"""
        if symbol not in self._cache:
            return []
        records = self._cache[symbol]
        return records[-days:] if len(records) > days else records

    def get_state_trajectory(self, symbol: str, days: int = 5) -> List[int]:
        """获取最近N天的状态序列（仅状态编号）。"""
        recent = self.get_recent_states(symbol, days)
        return [r.state for r in recent]

    def get_score_history(self, symbol: str, days: int = 5) -> List[int]:
        """获取最近N天的得分序列（用于sparkline）。"""
        recent = self.get_recent_states(symbol, days)
        return [r.score for r in recent]

    def get_conditions_history(self, symbol: str, days: int = 5) -> List[Dict[str, bool]]:
        """获取最近N天的三条件变化序列。"""
        recent = self.get_recent_states(symbol, days)
        return [r.conditions for r in recent]

    def to_dict(self) -> Dict:
        """序列化为字典格式，用于嵌入Dashboard HTML。"""
        result = {}
        for code, records in self._cache.items():
            result[code] = [
                {
                    "date": r.date,
                    "state": r.state,
                    "state_label": r.state_label,
                    "score": r.score,
                    "position_ratio": r.position_ratio,
                    "conditions": r.conditions,
                }
                for r in records
            ]
        return result

    def save_cache(self, path: str = "dashboard/data/history_states.json") -> str:
        """保存完整缓存为JSON文件。"""
        from datetime import datetime
        output = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "total_symbols": len(self._cache),
                "total_records": sum(len(v) for v in self._cache.values()),
            },
            "sectors": self.to_dict(),
        }
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(output, f, ensure_ascii=False)
        return path

    @staticmethod
    def _normalize_state(state):
        """标准化状态值：'3\'' → '3p'（JSON兼容）。"""
        if state == "3'" or state == "3p":
            return "3p"
        if isinstance(state, str) and state.isdigit():
            return int(state)
        return state

    @staticmethod
    def state_to_color(state) -> str:
        """状态→Dashboard颜色映射。"""
        return {
            1: "#6e7681", 2: "#8b949e", 3: "#42a5f5",
            4: "#26a69a", 5: "#d29922", "3p": "#da3633",
        }.get(state, "#6e7681")

    @staticmethod
    def trajectory_direction(states: List) -> str:
        """判断状态轨迹方向: up/down/stable/mixed。

        多赚钱：方向判断=自动过滤=只关注改善中的标的。
        少亏钱：方向判断=自动报警=及时发现恶化。
        """
        if len(states) < 2:
            return "stable"

        def state_rank(s):
            order = {1: 0, 2: 1, 3: 2, "3p": 2.5, 5: 3, 4: 4}
            return order.get(s, 0)

        ranks = [state_rank(s) for s in states]
        first_rank = ranks[0]
        last_rank = ranks[-1]

        # 检测双向波动：同时有向上和向下的状态变化
        has_up = any(ranks[i] > ranks[i-1] + 0.5 for i in range(1, len(ranks)))
        has_down = any(ranks[i] < ranks[i-1] - 0.5 for i in range(1, len(ranks)))

        if has_up and has_down:
            return "mixed"

        if last_rank > first_rank + 0.5:
            return "up"
        elif last_rank < first_rank - 0.5:
            return "down"
        else:
            if max(ranks) - min(ranks) > 1:
                return "mixed"
            return "stable"
