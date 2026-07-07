"""Display payload schema boundary for TFS v2."""

from __future__ import annotations


def validate_display_payload(payload: dict) -> dict:
    """Validate the minimal v2 display payload contract."""

    _require_dict(payload, "payload")
    meta = _require_dict(payload.get("meta"), "meta")
    _require(meta, "date", "meta")
    _require(meta, "run_id", "meta")
    regions = _require_list(payload.get("regions"), "regions")
    cards = _require_list(payload.get("cards"), "cards")
    card_ids = set()
    cards_by_id = {}
    for card in cards:
        _require_dict(card, "card")
        card_id = _require(card, "id", "card")
        _require(card, "type", f"card {card_id}")
        if _contains_html(card):
            raise ValueError(f"card {card_id} contains html-like content")
        card_ids.add(card_id)
        cards_by_id[card_id] = card

    for region in regions:
        _require_dict(region, "region")
        region_id = _require(region, "id", "region")
        _require(region, "title", f"region {region_id}")
        for card_id in _require_list(region.get("card_ids"), f"region {region_id}.card_ids"):
            if card_id not in card_ids:
                raise ValueError(f"region {region_id} references missing card {card_id}")

    validated = dict(payload)
    validated["cards_by_id"] = cards_by_id
    return validated


def validate_nav_payload(payload: dict) -> dict:
    """Validate the minimal v2 navigation payload contract."""

    _require_dict(payload, "payload")
    items = _require_list(payload.get("items"), "items")
    for item in items:
        _require_dict(item, "nav item")
        item_id = _require(item, "id", "nav item")
        if item.get("type") != "date_nav_card":
            raise ValueError(f"nav item {item_id} must be date_nav_card")
        _require_dict(item.get("line_time"), f"nav item {item_id}.line_time")
        _require_dict(item.get("line_market"), f"nav item {item_id}.line_market")
        _require_dict(item.get("line_leaders"), f"nav item {item_id}.line_leaders")
    return payload


def _require_dict(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict")
    return value


def _require_list(value, label: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _require(data: dict, key: str, label: str):
    value = data.get(key)
    if value in (None, ""):
        raise ValueError(f"{label}.{key} is required")
    return value


def _contains_html(value) -> bool:
    if isinstance(value, str):
        return "<" in value or ">" in value
    if isinstance(value, dict):
        return any(_contains_html(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_html(item) for item in value)
    return False
