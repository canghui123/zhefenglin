from types import SimpleNamespace

from services.pdf_generator import _get_path_c_auction_discount_rate


def test_path_c_auction_discount_rate_falls_back_to_sale_price_ratio():
    result = SimpleNamespace(
        input=SimpleNamespace(che300_value=100000),
        path_c=SimpleNamespace(sale_price=87650),
    )

    assert _get_path_c_auction_discount_rate(result) == 0.8765


def test_path_c_auction_discount_rate_prefers_explicit_rate():
    result = SimpleNamespace(
        input=SimpleNamespace(che300_value=100000),
        path_c=SimpleNamespace(sale_price=87650, auction_discount_rate=0.82),
    )

    assert _get_path_c_auction_discount_rate(result) == 0.82
