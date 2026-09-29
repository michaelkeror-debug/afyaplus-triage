import pytest

pytest.importorskip("mcp")
import logistics_mcp as lm  # noqa: E402


def test_version_resource_is_semver():
    parts = lm.version_current().split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)


def test_check_stock_known_item():
    r = lm.check_stock("C01", "amoxicillin")
    assert r["quantity"] == 40 and r["reorder_needed"] is False


def test_check_stock_zero_triggers_reorder():
    assert lm.check_stock("C04", "amoxicillin")["reorder_needed"] is True


def test_check_stock_normalises_item_name():
    assert lm.check_stock("C02", "  Malaria_Kits ")["quantity"] == 6


def test_unknown_clinic_and_item_return_errors():
    assert "error" in lm.check_stock("C99", "amoxicillin")
    assert "error" in lm.check_stock("C01", "paracetamol")


def test_list_low_stock():
    items = {x["item"] for x in lm.list_low_stock("C02")["low_stock"]}
    assert items == {"amoxicillin", "malaria_kits"}
    assert lm.list_low_stock("C03")["low_stock"] == []
