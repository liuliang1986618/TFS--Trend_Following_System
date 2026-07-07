import json
from pathlib import Path

import pandas as pd

from v2.data_layer import DataLayer
from v2.data_layer.fetcher import DataFetcher
from v2.data_layer.providers.akshare_em import AkshareEMProvider


class FakeRelationAkshare:
    @staticmethod
    def stock_board_industry_name_ths():
        return pd.DataFrame(
            [
                {"code": "881121", "name": "半导体"},
                {"code": "881155", "name": "软件服务"},
            ]
        )

    @staticmethod
    def stock_board_concept_name_ths():
        return pd.DataFrame(
            [
                {"code": "308614", "name": "人工智能"},
            ]
        )

    @staticmethod
    def stock_board_industry_cons_em(symbol):
        data = {
            "半导体": [
                {"代码": "300308", "名称": "中际旭创"},
                {"代码": "688981", "名称": "中芯国际"},
            ],
            "软件服务": [
                {"代码": "000001", "名称": "平安银行"},
            ],
        }
        return pd.DataFrame(data[symbol])

    @staticmethod
    def stock_board_concept_cons_em(symbol):
        data = {
            "人工智能": [
                {"代码": "300308", "名称": "中际旭创"},
                {"代码": "002230", "名称": "科大讯飞"},
            ],
        }
        return pd.DataFrame(data[symbol])


class FakeRealRelationAkshare:
    @staticmethod
    def stock_board_industry_name_ths():
        return pd.DataFrame([{"code": "881121", "name": "半导体"}])

    @staticmethod
    def stock_board_concept_name_ths():
        return pd.DataFrame([{"code": "308614", "name": "人工智能"}])

    @staticmethod
    def stock_board_industry_cons_em(symbol):
        raise AssertionError("default provider should use direct Eastmoney member fetch")

    @staticmethod
    def stock_board_concept_cons_em(symbol):
        raise AssertionError("default provider should use direct Eastmoney member fetch")


class FakeMultiSourceProvider:
    def fetch_relation_universe(self, source, kind):
        data = {
            ("eastmoney", "sector"): [{"code": "BK1036", "name": "半导体"}],
            ("eastmoney", "theme"): [{"code": "BK0800", "name": "人工智能"}],
            ("ths", "sector"): [{"code": "881121", "name": "半导体"}],
            ("ths", "theme"): [{"code": "308614", "name": "人工智能"}],
        }
        return data[(source, kind)]

    def fetch_relation_members(self, source, kind, item):
        data = {
            ("eastmoney", "sector", "BK1036"): [
                {"code": "300308", "name": "中际旭创"},
                {"code": "688981", "name": "中芯国际"},
            ],
            ("eastmoney", "theme", "BK0800"): [
                {"code": "002230", "name": "科大讯飞"},
                {"code": "300308", "name": "中际旭创"},
            ],
            ("ths", "sector", "881121"): [
                {"code": "300308", "name": "中际旭创"},
            ],
            ("ths", "theme", "308614"): [
                {"code": "002230", "name": "科大讯飞"},
            ],
        }
        return data[(source, kind, item["code"])]


def test_akshare_em_provider_normalizes_relation_universe_and_members():
    provider = AkshareEMProvider(ak_module=FakeRelationAkshare)

    sectors = provider.fetch_sector_universe()
    themes = provider.fetch_theme_universe()
    members = provider.fetch_sector_members("半导体")

    assert sectors == [{"code": "881121", "name": "半导体"}, {"code": "881155", "name": "软件服务"}]
    assert themes == [{"code": "308614", "name": "人工智能"}]
    assert members == [{"code": "300308", "name": "中际旭创"}, {"code": "688981", "name": "中芯国际"}]


def test_default_provider_fetches_members_through_direct_eastmoney_pages(monkeypatch):
    calls = []

    def fake_pages(fs, fields, max_pages=10):
        calls.append((fs, fields, max_pages))
        if fs == "m:90 t:2 f:!50":
            return [{"f12": "BK1036", "f14": "半导体"}]
        if fs == "b:BK1036":
            return [{"f12": "300308", "f14": "中际旭创"}]
        return []

    monkeypatch.setattr(AkshareEMProvider, "_fetch_em_pages", staticmethod(fake_pages))
    provider = AkshareEMProvider()

    members = provider.fetch_sector_members("半导体")

    assert members == [{"code": "300308", "name": "中际旭创"}]
    assert ("b:BK1036", "f12,f14", 5) in calls


def test_data_fetcher_update_relations_weekly_writes_versioned_current_relations(tmp_path):
    provider = AkshareEMProvider(ak_module=FakeRelationAkshare)
    fetcher = DataFetcher(data_dir=tmp_path, provider=provider)

    result = fetcher.update_relations_weekly(week="2026-W26")

    assert result["status"] == "completed"
    assert result["version"] == "2026-W26"
    assert result["sources"] == ["eastmoney"]
    assert result["checks"]["eastmoney"]["sector"]["total"] == 2
    assert result["checks"]["eastmoney"]["sector"]["success"] == 2
    assert result["checks"]["eastmoney"]["theme"]["total"] == 1
    assert result["checks"]["eastmoney"]["theme"]["success"] == 1

    current_path = tmp_path / "meta" / "relations" / "current.json"
    version_path = tmp_path / "meta" / "relations" / "eastmoney" / "2026-W26.json"
    source_current_path = tmp_path / "meta" / "relations" / "eastmoney" / "current.json"
    active_path = tmp_path / "meta" / "relations" / "active.json"
    assert current_path.exists()
    assert source_current_path.exists()
    assert version_path.exists()
    assert active_path.exists()

    current = json.loads(current_path.read_text(encoding="utf-8"))
    assert current["version"] == "2026-W26"
    assert current["source"] == "eastmoney"
    assert current["sector_members"]["881121"] == ["300308", "688981"]
    assert current["theme_members"]["308614"] == ["002230", "300308"]
    assert current["stock_profiles"]["300308"]["sectors"] == ["881121"]
    assert current["stock_profiles"]["300308"]["themes"] == ["308614"]

    active = json.loads(active_path.read_text(encoding="utf-8"))
    assert active == {"version": "2026-W26", "primary": "eastmoney", "fallback": []}

    layer = DataLayer(tmp_path, fetcher=fetcher)
    assert layer.get_sector_members("881121") == ["300308", "688981"]
    assert layer.get_theme_members("308614") == ["002230", "300308"]
    assert layer.get_stock_profile("300308")["themes"] == ["308614"]
    health = layer.check_relation_health("2026-W26")
    assert health["version"] == "2026-W26"
    assert health["source"] == "eastmoney"
    assert not any("missing" in issue for issue in health["issues"])


def test_data_fetcher_update_relations_weekly_writes_multiple_sources_and_active_primary(tmp_path):
    fetcher = DataFetcher(data_dir=tmp_path, provider=FakeMultiSourceProvider())

    result = fetcher.update_relations_weekly(week="2026-W26", sources=("eastmoney", "ths"))

    assert result["status"] == "completed"
    assert result["sources"] == ["eastmoney", "ths"]
    assert result["active_source"] == "eastmoney"
    assert (tmp_path / "meta" / "relations" / "eastmoney" / "current.json").exists()
    assert (tmp_path / "meta" / "relations" / "ths" / "current.json").exists()

    eastmoney = json.loads((tmp_path / "meta" / "relations" / "eastmoney" / "current.json").read_text(encoding="utf-8"))
    ths = json.loads((tmp_path / "meta" / "relations" / "ths" / "current.json").read_text(encoding="utf-8"))
    active = json.loads((tmp_path / "meta" / "relations" / "active.json").read_text(encoding="utf-8"))
    current = json.loads((tmp_path / "meta" / "relations" / "current.json").read_text(encoding="utf-8"))

    assert eastmoney["source"] == "eastmoney"
    assert ths["source"] == "ths"
    assert active == {"version": "2026-W26", "primary": "eastmoney", "fallback": ["ths"]}
    assert current["source"] == "eastmoney"
    assert current["sector_members"]["BK1036"] == ["300308", "688981"]


def test_data_layer_update_relations_weekly_delegates_to_fetcher(tmp_path):
    provider = AkshareEMProvider(ak_module=FakeRelationAkshare)
    fetcher = DataFetcher(data_dir=tmp_path, provider=provider)
    layer = DataLayer(tmp_path, fetcher=fetcher)

    result = layer.update_relations_weekly(week="2026-W26")

    assert result["status"] == "completed"
    assert layer.get_relation_version() == "2026-W26"


def test_relation_health_reports_inconsistent_reverse_mapping(tmp_path):
    relations_dir = tmp_path / "meta" / "relations"
    relations_dir.mkdir(parents=True)
    (relations_dir / "current.json").write_text(
        json.dumps(
            {
                "version": "2026-W26",
                "sectors": [{"code": "881121", "name": "半导体"}],
                "themes": [{"code": "308614", "name": "人工智能"}],
                "sector_members": {"881121": ["300308"]},
                "theme_members": {"308614": ["300308"]},
                "stock_profiles": {"300308": {"name": "中际旭创", "sectors": [], "themes": ["308614"]}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    health = DataLayer(tmp_path).check_relation_health("2026-W26")

    assert health["status"] == "warning"
    assert any("missing sector reverse" in issue for issue in health["issues"])


def test_update_relations_weekly_does_not_replace_current_when_update_fails(tmp_path):
    relations_dir = tmp_path / "meta" / "relations"
    relations_dir.mkdir(parents=True)
    (relations_dir / "current.json").write_text('{"version": "old", "sector_members": {"old": ["000001"]}}', encoding="utf-8")

    class FailingProvider(AkshareEMProvider):
        def __init__(self):
            pass

        def fetch_sector_universe(self):
            return [{"code": "881121", "name": "半导体"}]

        def fetch_theme_universe(self):
            return []

        def fetch_sector_members(self, name):
            raise RuntimeError("network down")

    fetcher = DataFetcher(data_dir=tmp_path, provider=FailingProvider())

    result = fetcher.update_relations_weekly(week="2026-W27")

    assert result["status"] == "partial"
    current = json.loads((relations_dir / "current.json").read_text(encoding="utf-8"))
    assert current["version"] == "old"
    assert not (relations_dir / "eastmoney" / "2026-W27.json").exists()
