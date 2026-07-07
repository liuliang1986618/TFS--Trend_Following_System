"""Stock, ETF, sector, and theme funnel orchestration for TFS v2."""

from __future__ import annotations


class FunnelRunner:
    def scan_stock_funnel(self, *args, **kwargs):
        raise NotImplementedError("Task 4 implements stock funnel scanning")

    def scan_etf_direct(self, *args, **kwargs):
        raise NotImplementedError("Task 4 implements ETF direct scanning")
