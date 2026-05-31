"""测试板块/题材成分股映射关系。"""
import pytest
from src.data.mappings import ConstituentMapping


class TestConstituentMapping:
    def test_add_and_query_sector_mapping(self):
        """添加板块成分股后能正确查询。"""
        mapping = ConstituentMapping()
        mapping.add_sector_constituents("BK0477", [
            {"symbol": "000001", "name": "平安银行"},
            {"symbol": "000002", "name": "万科A"},
        ])
        stocks = mapping.get_sector_stocks("BK0477")
        assert len(stocks) == 2
        assert stocks[0]["symbol"] == "000001"

    def test_get_all_sector_symbols(self):
        """获取板块下所有股票代码。"""
        mapping = ConstituentMapping()
        mapping.add_sector_constituents("BK0477", [
            {"symbol": "000001", "name": "平安银行"},
            {"symbol": "000002", "name": "万科A"},
        ])
        symbols = mapping.get_sector_symbols("BK0477")
        assert symbols == ["000001", "000002"]

    def test_add_theme_constituents(self):
        """添加题材成分股后能正确查询。"""
        mapping = ConstituentMapping()
        mapping.add_theme_constituents("GN300308", [
            {"symbol": "300308", "name": "中际旭创"},
            {"symbol": "300502", "name": "新易盛"},
        ])
        stocks = mapping.get_theme_stocks("GN300308")
        assert len(stocks) == 2

    def test_get_stock_sectors(self):
        """反向查询：一个股票属于哪些板块。"""
        mapping = ConstituentMapping()
        mapping.add_sector_constituents("BK0477", [
            {"symbol": "000001", "name": "平安银行"},
        ])
        mapping.add_sector_constituents("BK0488", [
            {"symbol": "000001", "name": "平安银行"},
        ])
        sectors = mapping.get_stock_sectors("000001")
        assert "BK0477" in sectors
        assert "BK0488" in sectors

    def test_get_stock_themes(self):
        """反向查询：一个股票属于哪些题材。"""
        mapping = ConstituentMapping()
        mapping.add_theme_constituents("GN300308", [
            {"symbol": "300308", "name": "中际旭创"},
        ])
        themes = mapping.get_stock_themes("300308")
        assert "GN300308" in themes

    def test_empty_mapping_returns_empty(self):
        """空映射查询不崩溃。"""
        mapping = ConstituentMapping()
        assert mapping.get_sector_stocks("NONEXIST") == []
        assert mapping.get_stock_sectors("NONEXIST") == []
        assert mapping.sector_count == 0
        assert mapping.theme_count == 0
