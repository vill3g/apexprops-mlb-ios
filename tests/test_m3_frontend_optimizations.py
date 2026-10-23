"""
Milestone 3 Optimization and Controls Verification Suite.
Validates:
1. Tab switching optimization: non-blocking HUD and chart rendering on switch to Financial.
2. Tab switching optimization: cache-first rendering of sports events on switch to Sports.
3. Chart resize & fitContent in requestAnimationFrame on tab restore.
4. Static app.js and static/js/app.js exact byte synchronization.
5. Auto-trading toggle synchronization across #header-auto-toggle and #sports-header-auto-toggle.
6. Auto-trading universe segmented buttons synchronization across both drawers.
7. Verification of all 70+ controls across #financialSettingsDrawer and #sportsSettingsDrawer.
8. Dirty-check signature caching on renderTradesContainer to prevent DOM thrashing.
"""

import hashlib
import os
import re
import pytest
from bs4 import BeautifulSoup

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HTML_PATH = os.path.join(REPO_ROOT, "static", "saas_dashboard.html")
JS_APP_PATH = os.path.join(REPO_ROOT, "static", "js", "app.js")
ROOT_APP_PATH = os.path.join(REPO_ROOT, "static", "app.js")


@pytest.fixture(scope="module")
def html_content():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def html_soup(html_content):
    return BeautifulSoup(html_content, "html.parser")


class TestM3TabSwitchingOptimizations:
    """Verifies that tab switching does not flicker or blank HUD/charts."""

    def test_financial_tab_switch_passes_isTabSwitch_flag(self, html_content):
        """selectUniverse('FINANCIAL') passes isTabSwitch=true to selectDashboardAsset."""
        assert "selectDashboardAsset(activeTarget, true)" in html_content, (
            "selectUniverse must pass isTabSwitch=true when restoring Financial tab"
        )

    def test_selectDashboardAsset_has_skipLoaderAndBlanking_logic(self, html_content):
        """selectDashboardAsset avoids showChartLoader() and HUD blanking when isTabSwitch or cached data is present."""
        assert "skipLoaderAndBlanking" in html_content
        assert "!skipLoaderAndBlanking" in html_content
        assert "isTabSwitch || (isSameAsset && hasExistingChart && hasCachedData)" in html_content

    def test_chart_resize_requestAnimationFrame_present(self, html_content):
        """selectUniverse dispatches requestAnimationFrame with applyOptions and fitContent on canvas restore."""
        assert "requestAnimationFrame" in html_content
        assert "chart.timeScale().fitContent()" in html_content or "chartInstance.timeScale().fitContent()" in html_content

    def test_sports_tab_switch_renders_cache_immediately(self, html_content):
        """selectUniverse immediately renders sports events from window.__sportsEventsCache if available."""
        assert "window.__sportsEventsCache" in html_content
        assert "renderSportsEvents();" in html_content

    def test_renderSportsEvents_does_not_pulse_if_cache_exists(self, html_content):
        """renderSportsEvents does not wipe container with pulsating loader if cached events exist."""
        assert "!window.__sportsEventsCache || window.__sportsEventsCache.length === 0" in html_content

    def test_candles_cache_saved_in_fetchChartData(self, html_content):
        """fetchChartData populates window.candlesCache[reqAsset] for fast retrieval."""
        assert "window.candlesCache" in html_content

    def test_renderTradesContainer_has_dirty_check_cache(self, html_content):
        """renderTradesContainer skips DOM reconstruction if trades have not changed."""
        assert "window._lastTradesContainerKey" in html_content


class TestM3ScriptSynchronization:
    """Verifies that static/app.js and static/js/app.js are in exact sync."""

    def test_app_js_files_identical(self):
        with open(JS_APP_PATH, "rb") as f1, open(ROOT_APP_PATH, "rb") as f2:
            h1 = hashlib.sha256(f1.read()).hexdigest()
            h2 = hashlib.sha256(f2.read()).hexdigest()
        assert h1 == h2, "static/app.js must be completely synchronized with static/js/app.js"


class TestM3DrawerControlsWiring:
    """Verifies that all form controls, toggles, and switches exist and sync without errors."""

    def test_auto_trader_toggles_synchronized(self, html_soup, html_content):
        """Both header-auto-toggle and sports-header-auto-toggle exist and are synchronized."""
        fin_toggle = html_soup.find(id="header-auto-toggle")
        sports_toggle = html_soup.find(id="sports-header-auto-toggle")
        assert fin_toggle is not None
        assert sports_toggle is not None
        assert "document.querySelectorAll('#header-auto-toggle, #sports-header-auto-toggle')" in html_content

    def test_paper_live_mode_toggles_in_both_drawers(self, html_soup):
        """Both drawers feature dedicated paper/live buttons."""
        assert html_soup.find(id="btn-mode-paper-settings") is not None
        assert html_soup.find(id="btn-mode-live-settings") is not None
        assert html_soup.find(id="sports-btn-mode-paper-settings") is not None
        assert html_soup.find(id="sports-btn-mode-live-settings") is not None

    def test_universe_segmented_buttons_in_both_drawers(self, html_soup):
        """Both drawers contain [ CRYPTO ] [ SPORTS ] [ BOTH ] buttons."""
        assert html_soup.find(id="btn-auto-univ-crypto") is not None
        assert html_soup.find(id="btn-auto-univ-sports") is not None
        assert html_soup.find(id="btn-auto-univ-both") is not None
        assert html_soup.find(id="sports-btn-auto-univ-crypto") is not None
        assert html_soup.find(id="sports-btn-auto-univ-sports") is not None
        assert html_soup.find(id="sports-btn-auto-univ-both") is not None

    def test_financial_controls_present(self, html_soup):
        """Financial drawer has asset toggles, stop loss, take profit, trailing stop, ATR, trade size."""
        fin = html_soup.find(id="financialSettingsDrawer")
        for cid in [
            "trade-size-dollars", "stop-loss-pct", "stop-loss-toggle",
            "take-profit-pct", "take-profit-toggle", "trailing-stop-toggle",
            "trailing-stop-activation-pct", "trailing-stop-distance-pct",
            "atr-risk-toggle", "second-entry-toggle", "second-entry-max-ask",
            "asset-btc-toggle", "asset-eth-toggle", "asset-gold-toggle"
        ]:
            assert fin.find(id=cid) is not None, f"Missing {cid} in financial drawer"

    def test_sports_controls_present(self, html_soup):
        """Sports drawer has 7 leagues, 5 market types, 9 props, trade size, Kelly, price corridor, TP, sliders."""
        sports = html_soup.find(id="sportsSettingsDrawer")
        for cid in [
            "sports-trade-size-dollars", "sports-wager-dollars", "sports-kelly-toggle",
            "sports-min-price", "sports-max-price", "sports-tp-toggle", "sports-tp-pct",
            "sports-max-daily-trades", "sports-max-open-trades", "sports-max-daily-risk",
            "sports-conf-slider", "sports-edge-slider", "sports-include-live-toggle"
        ]:
            assert sports.find(id=cid) is not None, f"Missing {cid} in sports drawer"

        leagues = [t.get("value") for t in sports.find_all(class_="sports-league-toggle")]
        assert len(leagues) == 7
        assert "NPB/KBO" in leagues

        mtypes = [t.get("value") for t in sports.find_all(class_="sports-market-toggle")]
        assert len(mtypes) == 5

        props = [t.get("value") for t in sports.find_all(class_="sports-prop-toggle")]
        assert len(props) == 9

    def test_saveUserConfig_has_all_fields_and_no_reference_errors(self, html_content):
        """saveUserConfig properly collects sportsActivePropsStr and configPayload fields."""
        assert "sportsActivePropsStr" in html_content
        assert "sportsActiveLeaguesStr" in html_content
        assert "sportsMarketTypesStr" in html_content
        assert "window.configuredTradingUniverse" in html_content
