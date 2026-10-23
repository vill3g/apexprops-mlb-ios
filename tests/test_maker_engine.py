import sys
sys.path.insert(0, '.')
from backend.btc.maker_engine import compute_maker_limit_price, get_execution_urgency
from backend.btc.kalshi_trader import KalshiTrader

def test_maker_engine():
    # Test 1: Wide spread maker price
    m_wide = {'yes_bid': 0.44, 'yes_ask': 0.50}
    px, is_maker = compute_maker_limit_price(m_wide, 'yes', urgency='MAKER')
    print(f"Test 1 Wide (0.44/0.50): px={px}, is_maker={is_maker}")
    assert px == 0.45 and is_maker is True, f"Expected 0.45 True, got {px} {is_maker}"

    # Test 2: 2-cent spread maker price
    m_two = {'yes_bid': 0.48, 'yes_ask': 0.50}
    px, is_maker = compute_maker_limit_price(m_two, 'yes', urgency='MAKER')
    print(f"Test 2 Two-cent (0.48/0.50): px={px}, is_maker={is_maker}")
    assert px == 0.49 and is_maker is True, f"Expected 0.49 True, got {px} {is_maker}"

    # Test 3: 1-cent spread maker price
    m_one = {'yes_bid': 0.49, 'yes_ask': 0.50}
    px, is_maker = compute_maker_limit_price(m_one, 'yes', urgency='MAKER')
    print(f"Test 3 One-cent (0.49/0.50): px={px}, is_maker={is_maker}")
    assert px == 0.49 and is_maker is True, f"Expected 0.49 True, got {px} {is_maker}"

    # Test 4: Taker urgency overrides
    px, is_maker = compute_maker_limit_price(m_wide, 'yes', urgency='TAKER')
    print(f"Test 4 Taker Override: px={px}, is_maker={is_maker}")
    assert px == 0.50 and is_maker is False, f"Expected 0.50 False, got {px} {is_maker}"

    # Test 5: Urgency rules
    assert get_execution_urgency(sec_left=60) == 'TAKER'
    assert get_execution_urgency(sec_left=300, regime='MOMENTUM_SURFER') == 'TAKER'
    assert get_execution_urgency(sec_left=300, regime='SNIPER', forecast={'prob': 85}) == 'TAKER'
    assert get_execution_urgency(sec_left=300, regime='SNIPER', forecast={'prob': 65}) == 'MAKER'
    print("Test 5 Urgency Rules: PASSED")

    # Test 6: Paper maker execution without taker slippage tax
    kt = KalshiTrader()
    res = kt.place_order(ticker='KXBTC15M-TEST', side='yes', count=1, limit_price_dollars=0.45, dry_run=True, post_only=True)
    print(f"Test 6 Paper Maker: success={res.get('success')}, filled_px={res.get('filled_price')}, source={res.get('fill_source')}")
    assert res.get('success') is True
    assert res.get('filled_price') == 0.45
    assert res.get('fill_source') == 'maker_passive_limit'

    print("ALL MAKER ENGINE TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_maker_engine()
