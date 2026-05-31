"""板块/题材成分股映射关系管理。

为什么用dict而不是pandas？
→ 多赚钱：查询操作远多于写入操作。dict的O(1)查询比DataFrame筛选快得多。
  在第三层个股筛选中，需要频繁反向查询"某个股票属于哪些上涨板块"，
  每次查询节省几十ms，300-500只个股就能节省几秒——更快完成筛选 = 更早发现机会。

为什么同时维护正向和反向映射？
→ 多赚钱(正向)：从板块快速找到所有成分股，驱动第三层个股筛选。
→ 少亏钱(反向)：快速判断个股是否有板块支撑。无板块支撑的个股趋势不可靠，
  排除它们 = 降低假突破被套的概率。
"""
from typing import List, Dict, Set


class ConstituentMapping:
    """管理板块→成分股、题材→成分股的双向映射关系。

    三类映射：
      1. code → [constituents]   正向：板块/题材有哪些股票
      2. symbol → [sectors]      反向：股票属于哪些板块
      3. symbol → [themes]       反向：股票属于哪些题材
    """

    def __init__(self):
        self._sector_stocks: Dict[str, List[dict]] = {}
        self._theme_stocks: Dict[str, List[dict]] = {}
        self._stock_sectors: Dict[str, Set[str]] = {}
        self._stock_themes: Dict[str, Set[str]] = {}

    def add_sector_constituents(self, bk_code: str, constituents: List[dict]):
        """添加板块成分股。

        constituents: [{"symbol": "...", "name": "..."}, ...]
        """
        self._sector_stocks[bk_code] = constituents
        for c in constituents:
            sym = c["symbol"]
            if sym not in self._stock_sectors:
                self._stock_sectors[sym] = set()
            self._stock_sectors[sym].add(bk_code)

    def add_theme_constituents(self, gn_code: str, constituents: List[dict]):
        """添加题材成分股。"""
        self._theme_stocks[gn_code] = constituents
        for c in constituents:
            sym = c["symbol"]
            if sym not in self._stock_themes:
                self._stock_themes[sym] = set()
            self._stock_themes[sym].add(gn_code)

    def get_sector_stocks(self, bk_code: str) -> List[dict]:
        """获取板块下所有成分股。"""
        return self._sector_stocks.get(bk_code, [])

    def get_sector_symbols(self, bk_code: str) -> List[str]:
        """获取板块下所有股票代码。"""
        return [c["symbol"] for c in self.get_sector_stocks(bk_code)]

    def get_theme_stocks(self, gn_code: str) -> List[dict]:
        """获取题材下所有成分股。"""
        return self._theme_stocks.get(gn_code, [])

    def get_theme_symbols(self, gn_code: str) -> List[str]:
        """获取题材下所有股票代码。"""
        return [c["symbol"] for c in self.get_theme_stocks(gn_code)]

    def get_stock_sectors(self, symbol: str) -> List[str]:
        """获取某股票所属的所有板块代码。"""
        return list(self._stock_sectors.get(symbol, set()))

    def get_stock_themes(self, symbol: str) -> List[str]:
        """获取某股票所属的所有题材代码。"""
        return list(self._stock_themes.get(symbol, set()))

    @property
    def sector_count(self) -> int:
        return len(self._sector_stocks)

    @property
    def theme_count(self) -> int:
        return len(self._theme_stocks)
