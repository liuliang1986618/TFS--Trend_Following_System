"""akshare数据源实现 — 主数据源。

数据获取策略（设计文档§4.3）：
  - 板块指数：东方财富/同花顺行业板块接口
  - 板块日K：stock_board_industry_index_ths()
  - 个股日K：stock_zh_a_hist() 批量获取（前复权）
  - 题材指数：stock_board_concept_hist_ths()
  - ETF：fund_etf_spot_em() + fund_etf_hist_em()

为什么选akshare作为主数据源？
→ 多赚钱：akshare封装了东方财富、同花顺等免费公开API，支持批量拉取
  A股全市场数据。批量拉取意味着每天的数据更新能在10秒内完成，
  快速的数据更新 = 更早发现趋势变化 = 抢占先机。

为什么需要限速？
→ 少亏钱：无限制请求会被API方封禁IP，导致数据源不可用。
  限速确保数据源的持续可用性。
"""
import time
from typing import List, Optional
import pandas as pd
import akshare as ak

from .base import BaseProvider, ProviderConfig


class AkshareProvider(BaseProvider):
    """akshare数据源实现。

    所有接口均直接调用akshare封装的方法。
    限速由ProviderConfig.rate_limit_per_sec控制。
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config or ProviderConfig(name="akshare"))

    def _rate_limit(self):
        """限速控制，避免被封IP。

        为什么需要这个？
        → 少亏钱：被封IP = 数据源中断 = 无法做出交易决策。
        """
        time.sleep(1.0 / self.config.rate_limit_per_sec)

    def fetch_sector_indices(self) -> pd.DataFrame:
        """获取同花顺行业板块指数列表（含板块代码BK）。

        → 多赚钱：板块是漏斗第一层，板块列表是整个选股链路的起点。
        """
        self._rate_limit()
        df = ak.stock_board_industry_name_ths()
        df = df.rename(columns={
            "代码": "bk_code",
            "名称": "sector_name",
        })
        return df[["bk_code", "sector_name"]]

    def fetch_sector_daily(self, bk_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取板块指数日K。

        → 多赚钱：板块指数日K是识别板块趋势的原始数据。
        """
        self._rate_limit()
        df = ak.stock_board_industry_index_ths(
            symbol=bk_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        return self._normalize_ohlcv(df)

    def fetch_sector_daily_batch(self, bk_codes: List[str], start_date: str, end_date: str) -> dict:
        """批量获取板块日K。遍历板块代码逐个拉取。

        → 多赚钱：批量获取减少总耗时。每个板块独立try/catch，
          一个失败不影响其他——减少单点故障的损失。
        """
        result = {}
        for code in bk_codes:
            try:
                result[code] = self.fetch_sector_daily(code, start_date, end_date)
            except Exception as e:
                print(f"[WARN] fetch_sector_daily failed for {code}: {e}")
                continue
        return result

    def fetch_sector_constituents(self, bk_code: str) -> pd.DataFrame:
        """获取板块成分股列表。

        → 多赚钱：板块→成分股映射是漏斗第二→三层的桥梁。
          没有成分股映射就无法在上涨板块中选个股。
        """
        self._rate_limit()
        df = ak.stock_board_industry_cons_ths(symbol=bk_code)
        df = df.rename(columns={
            "代码": "symbol",
            "名称": "name",
        })
        return df[["symbol", "name"]]

    def fetch_theme_indices(self) -> pd.DataFrame:
        """获取同花顺概念题材指数列表（含题材代码GN）。

        → 多赚钱：题材比板块更精准，同一板块内高景气题材的涨幅
          往往是板块的2-3倍。题材是超额收益的核心来源。
        """
        self._rate_limit()
        df = ak.stock_board_concept_name_ths()
        df = df.rename(columns={
            "代码": "gn_code",
            "名称": "theme_name",
        })
        return df[["gn_code", "theme_name"]]

    def fetch_theme_daily(self, gn_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取题材指数日K。

        → 多赚钱：题材日K是判断题材生命阶段的数据源。
        """
        self._rate_limit()
        df = ak.stock_board_concept_hist_ths(
            symbol=gn_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        return self._normalize_ohlcv(df)

    def fetch_theme_constituents(self, gn_code: str) -> pd.DataFrame:
        """获取题材成分股列表。

        → 多赚钱：题材成分股是漏斗第三层选股的范围，
          也是龙头识别的基础数据。
        """
        self._rate_limit()
        df = ak.stock_board_concept_cons_ths(symbol=gn_code)
        df = df.rename(columns={
            "代码": "symbol",
            "名称": "name",
        })
        return df[["symbol", "name"]]

    def fetch_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取个股日K（前复权）。

        → 多赚钱：前复权确保价格序列的连续性，避免因除权除息
          导致的假突破/假跌破信号。
        """
        self._rate_limit()
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",  # 前复权
        )
        return self._normalize_ohlcv(df)

    def fetch_stock_daily_batch(self, symbols: List[str], start_date: str, end_date: str) -> dict:
        """批量获取个股日K。

        → 多赚钱：漏斗第三层需处理300-500只个股，批量获取+容错
          确保单个失败不影响全局。
        """
        result = {}
        for sym in symbols:
            try:
                result[sym] = self.fetch_stock_daily(sym, start_date, end_date)
            except Exception as e:
                print(f"[WARN] fetch_stock_daily failed for {sym}: {e}")
                continue
        return result

    def fetch_etf_list(self) -> pd.DataFrame:
        """获取ETF列表，并分类为A/B/C类型。

        类型A: 板块ETF（如半导体ETF、通信ETF）→ 适用本策略
        类型B: 跨板块/题材ETF（如新能源ETF）→ 独立判断
        类型C: 宽基/策略ETF（如沪深300ETF）→ 不适用，跳过

        → 少亏钱：过滤掉C类宽基ETF，避免在不适用本策略的标的上投入资金。
        """
        self._rate_limit()
        df = ak.fund_etf_spot_em()
        result = df[["代码", "名称"]].copy()
        result.columns = ["symbol", "name"]

        broad_keywords = ["沪深300", "中证500", "上证50", "创业板", "科创50",
                          "红利", "低波", "价值", "成长", "等权"]
        industry_keywords = ["半导体", "芯片", "通信", "医药", "白酒", "军工",
                             "银行", "券商", "保险", "地产", "有色", "煤炭",
                             "新能源", "光伏", "锂电", "风电"]

        def classify(row):
            name = row["name"]
            if any(kw in name for kw in broad_keywords):
                return "C"
            elif any(kw in name for kw in industry_keywords):
                return "A"
            else:
                return "B"

        result["etf_type"] = result.apply(classify, axis=1)
        return result

    def fetch_etf_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取ETF日K。

        → 多赚钱：ETF交易成本低、无单只股票暴雷风险。
          ETF直筛路径是漏斗主路径的重要补充。
        """
        self._rate_limit()
        df = ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        return self._normalize_ohlcv(df)

    def _normalize_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """将akshare返回的DataFrame标准化为统一格式。

        标准化原因：
        → 少亏钱：统一的数据格式意味着趋势引擎不需要猜测列名，
          不会因为列名不一致导致条件判断出错。
          如果'收盘'和'close'混用，条件判断可能静默失败=错误交易信号。

        Returns:
            DataFrame with columns: date(index), open, high, low, close, volume
        """
        # 日期列的各种可能名称
        date_candidates = ["日期", "date", "时间", "trade_date"]
        ohlcv_map = {
            "开盘": "open", "open": "open",
            "最高": "high", "high": "high",
            "最低": "low", "low": "low",
            "收盘": "close", "close": "close",
            "成交量": "volume", "volume": "volume",
        }

        df = df.copy()
        # 重命名列
        rename = {}
        for col in df.columns:
            if col in ohlcv_map:
                rename[col] = ohlcv_map[col]
            elif col in date_candidates:
                rename[col] = "date"
        df.rename(columns=rename, inplace=True)

        # 设置date为索引
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)

        # 确保所有数值列都是float/int
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = df[col].astype(float)
        if "volume" in df.columns:
            df["volume"] = df["volume"].astype(int)

        return df[["open", "high", "low", "close", "volume"]]
