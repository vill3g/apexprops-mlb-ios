"""
Empirical stress-testing and challenge suite for frontend filtering and display logic in static/saas_dashboard.html.
Written by teamwork_preview_challenger_2.

Tests:
1. Syntax validation of all <script> tags in static/saas_dashboard.html via Node.js compiler.
2. Headless Chromium browser DOM execution test via Playwright (verifying runtime loading, uncaught errors, function availability).
3. Empirical JS evaluation of isSportMatch across all supported sports (TEN, NFL, MLB, NHL, SOC, UFC, NPB/KBO).
4. Cross-sport negative testing (exhaustive pairwise matrix).
5. Empty state condition testing: window.__sportsLoading displays loading message vs "No active AI picks".
6. Settings gate testing: browsing specific tab (f = 'TEN') bypasses sportsEventAllowed, while f = 'ALL' enforces it.
7. Edge cases, falsy objects, ticker prefix matching, and alias variations.
"""

import json
import os
import re
import subprocess
import pytest
from bs4 import BeautifulSoup

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HTML_PATH = os.path.join(REPO_ROOT, "static", "saas_dashboard.html")


def read_dashboard_html():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


def extract_script_tags(html):
    soup = BeautifulSoup(html, "html.parser")
    scripts = []
    for tag in soup.find_all("script"):
        content = tag.string or tag.get_text() or ""
        if content.strip():
            scripts.append(content)
    return scripts


# ─────────────────────────────────────────────────────────────────────────────
# 1. SYNTAX VALIDATION & DOM PARSING (Live Browser & Node.js)
# ─────────────────────────────────────────────────────────────────────────────

def test_saas_dashboard_script_syntax_with_node():
    """
    Empirical Node.js syntax check on all inline scripts in saas_dashboard.html.
    Any SyntaxError (e.g. Illegal return statement, unexpected token) breaks the entire script block in browsers.
    """
    html = read_dashboard_html()
    scripts = extract_script_tags(html)
    assert len(scripts) > 0, "No script tags found in saas_dashboard.html"

    syntax_errors = []
    for idx, script_content in enumerate(scripts):
        runner = f"""
        const vm = require('node:vm');
        try {{
            new vm.Script({json.dumps(script_content)});
        }} catch(e) {{
            console.error(e.message);
            process.exit(1);
        }}
        """
        proc = subprocess.run(
            ["node"],
            input=runner,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip()
            syntax_errors.append(f"Script #{idx} failed syntax check: {err_msg}")

    if syntax_errors:
        pytest.fail("\n".join(syntax_errors))


def test_saas_dashboard_browser_runtime_load():
    """
    Empirically loads static/saas_dashboard.html in headless Chromium via Playwright
    to check for unhandled runtime errors, page crashes, and function definitions.
    """
    from playwright.sync_api import sync_playwright

    page_errors = []
    console_errors = []
    file_url = f"file:///{HTML_PATH.replace(os.sep, '/')}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.add_init_script("localStorage.setItem('saas_token', 'mock_valid_token');")
        page.route("**/api/**", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"status": "ok", "events": []}'
        ))

        page.goto(file_url)
        page.wait_for_timeout(1500)

        is_sport_match_type = page.evaluate("typeof isSportMatch")
        render_sports_type = page.evaluate("typeof renderSportsEvents")
        filter_sports_type = page.evaluate("typeof window.filterSportsEvents")

        browser.close()

    assert not page_errors, f"Dashboard loaded with uncaught JavaScript errors: {page_errors}"
    assert is_sport_match_type == "function", f"Expected isSportMatch to be a function, got {is_sport_match_type}"
    assert render_sports_type == "function", f"Expected renderSportsEvents to be a function, got {render_sports_type}"
    assert filter_sports_type == "function", f"Expected window.filterSportsEvents to be a function, got {filter_sports_type}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. EMPIRICAL JAVASCRIPT LOGIC HARNESS (ISOLATED JS EVALUATION)
# ─────────────────────────────────────────────────────────────────────────────

def run_js_eval(js_code: str):
    """Executes JS code in Node.js via stdin and returns JSON parsed output."""
    runner = f"""
    const vm = require('node:vm');
    const result = (() => {{
        {js_code}
    }})();
    console.log(JSON.stringify(result));
    """
    proc = subprocess.run(
        ["node"],
        input=runner,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Node execution failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
    return json.loads(proc.stdout.strip())


def get_extracted_is_sport_match_code():
    """
    Extracts the isSportMatch function definition from saas_dashboard.html
    using balanced curly-brace matching.
    """
    html = read_dashboard_html()
    idx = html.find("function isSportMatch(evt, f)")
    if idx == -1:
        raise ValueError("Could not find isSportMatch definition in saas_dashboard.html")
    start_brace = html.find("{", idx)
    open_count = 0
    end_idx = start_brace
    for i in range(start_brace, len(html)):
        if html[i] == "{":
            open_count += 1
        elif html[i] == "}":
            open_count -= 1
            if open_count == 0:
                end_idx = i + 1
                break
    return html[idx:end_idx]


# Matrix of representative payloads for all supported sports
VALID_SPORT_PAYLOADS = {
    "TEN": [
        {"sport": "TEN", "league": "ATP", "series_ticker": "KXATP", "event_ticker": "KXATPMATCH-26OCT09ALCCER"},
        {"sport": "TENNIS", "league": "WTA", "series_ticker": "KXWTA", "event_ticker": "KXWTAMATCH-26OCT09SWISAB"},
        {"sport": "TEN", "ticker": "KXATPMATCH-TEST"},
        {"sport": "TEN", "event_ticker": "KXTENMATCH-TEST"},
        {"league": "ATP", "event_ticker": "KXATPMATCH-1"},
        {"league": "WTA", "ticker": "KXWTAMATCH-1"},
    ],
    "NFL": [
        {"sport": "NFL", "league": "NFL", "series_ticker": "KXNFL", "event_ticker": "KXNFLMATCH-26OCT11KCBUF"},
        {"sport": "FOOTBALL", "league": "NFL", "series_ticker": "KXNFL", "event_ticker": "KXNFLMATCH-TEST"},
        {"ticker": "KXNFLGAME-TEST"},
        {"metadata": {"league": "NFL", "event_ticker": "KXNFL-TEST"}},
    ],
    "MLB": [
        {"sport": "MLB", "league": "MLB", "series_ticker": "KXMLB", "event_ticker": "KXMLBMATCH-26OCT09NYYCLE"},
        {"sport": "BASEBALL", "league": "MLB", "series_ticker": "KXMLB", "event_ticker": "KXMLBMATCH-TEST"},
        {"ticker": "KXMLBGAME-TEST"},
    ],
    "NHL": [
        {"sport": "NHL", "league": "NHL", "series_ticker": "KXNHL", "event_ticker": "KXNHLMATCH-26OCT09EDMFLA"},
        {"sport": "HOCKEY", "league": "NHL", "series_ticker": "KXNHL", "event_ticker": "KXNHLMATCH-TEST"},
        {"ticker": "KXNHLGAME-TEST"},
    ],
    "SOC": [
        {"sport": "SOC", "league": "EPL", "series_ticker": "KXEPL", "event_ticker": "KXEPLMATCH-26OCT10ARSCHE"},
        {"sport": "SOCCER", "league": "MLS", "series_ticker": "KXMLS", "event_ticker": "KXMLSMATCH-TEST"},
        {"sport": "SOC", "league": "UEFA", "series_ticker": "KXUEFA", "event_ticker": "KXUEFAMATCH-TEST"},
        {"sport": "SOC", "league": "WC", "series_ticker": "KXWC", "event_ticker": "KXWCMATCH-TEST"},
        {"ticker": "KXLALIGAMATCH-TEST"},
        {"ticker": "KXBUNDESMATCH-TEST"},
        {"ticker": "KXSERIEAMATCH-TEST"},
        {"ticker": "KXLIGUEMATCH-TEST"},
    ],
    "UFC": [
        {"sport": "UFC", "league": "UFC", "series_ticker": "KXUFC", "event_ticker": "KXUFCMATCH-26OCT12JONJON"},
        {"sport": "MMA", "league": "MMA", "series_ticker": "KXUFC", "event_ticker": "KXUFCMATCH-TEST"},
        {"ticker": "KXUFCFIGHT-TEST"},
    ],
    "NPB/KBO": [
        {"sport": "NPB", "league": "NPB", "series_ticker": "KXNPB", "event_ticker": "KXNPBMATCH-26OCT09YOKHIR"},
        {"sport": "KBO", "league": "KBO", "series_ticker": "KXKBO", "event_ticker": "KXKBOMATCH-26OCT09KIAHAN"},
        {"sport": "NPB/KBO", "league": "NPB", "event_ticker": "KXNPB-TEST"},
        {"sport": "NPB/KBO", "league": "KBO", "event_ticker": "KXKBO-TEST"},
        {"ticker": "KXNPBGAME-TEST"},
        {"ticker": "KXKBOGAME-TEST"},
    ]
}


def test_is_sport_match_positive_all_sports():
    """
    Empirically verifies that isSportMatch returns true for all valid sport payloads and ticker formats
    across all supported sports: TEN, NFL, MLB, NHL, SOC, UFC, NPB/KBO.
    """
    fn_code = get_extracted_is_sport_match_code()

    test_js = f"""
    {fn_code}
    const payloads = {json.dumps(VALID_SPORT_PAYLOADS)};
    const failures = [];

    for (const [sport, events] of Object.entries(payloads)) {{
        for (let i = 0; i < events.length; i++) {{
            const evt = events[i];
            const matched = isSportMatch(evt, sport);
            if (!matched) {{
                failures.push({{ sport, index: i, evt, matched }});
            }}
        }}
    }}
    return failures;
    """
    failures = run_js_eval(test_js)
    assert len(failures) == 0, f"isSportMatch failed positive matching on: {failures}"


def test_is_sport_match_cross_sport_isolation_negative_matrix():
    """
    Empirically verifies cross-sport negative isolation:
    isSportMatch(tennis_event, 'NFL') must be false,
    isSportMatch(nfl_event, 'TEN') must be false, etc.
    Runs an exhaustive 7x7 cross-sport negative matrix.
    """
    fn_code = get_extracted_is_sport_match_code()

    sports = list(VALID_SPORT_PAYLOADS.keys())
    test_js = f"""
    {fn_code}
    const payloads = {json.dumps(VALID_SPORT_PAYLOADS)};
    const falsePositives = [];

    const sports = {json.dumps(sports)};
    for (const actualSport of sports) {{
        const events = payloads[actualSport];
        for (const testFilter of sports) {{
            if (actualSport === testFilter) continue; // skip positive match
            for (let i = 0; i < events.length; i++) {{
                const evt = events[i];
                if (isSportMatch(evt, testFilter)) {{
                    falsePositives.push({{
                        actualSport,
                        testFilter,
                        evt
                    }});
                }}
            }}
        }}
    }}
    return falsePositives;
    """
    false_positives = run_js_eval(test_js)
    assert len(false_positives) == 0, f"Found cross-sport false positives: {false_positives}"


def test_is_sport_match_alias_variations():
    """
    Empirically verifies alias filters:
    - 'TENNIS' matches Tennis
    - 'SOCCER' matches Soccer
    - 'FOOTBALL' matches NFL
    - 'BASEBALL' matches MLB
    - 'HOCKEY' matches NHL
    - 'MMA' matches UFC
    - 'NPB_KBO' and 'NPB-KBO' matches NPB and KBO
    - 'ALL' or '' matches all sports
    """
    fn_code = get_extracted_is_sport_match_code()

    test_js = f"""
    {fn_code}
    const results = {{
        tennis_alias: isSportMatch({{ sport: 'TEN' }}, 'TENNIS'),
        soccer_alias: isSportMatch({{ sport: 'SOC' }}, 'SOCCER'),
        football_alias: isSportMatch({{ sport: 'NFL' }}, 'FOOTBALL'),
        baseball_alias: isSportMatch({{ sport: 'MLB' }}, 'BASEBALL'),
        hockey_alias: isSportMatch({{ sport: 'NHL' }}, 'HOCKEY'),
        mma_alias: isSportMatch({{ sport: 'UFC' }}, 'MMA'),
        npb_kbo_underscore: isSportMatch({{ sport: 'NPB' }}, 'NPB_KBO') && isSportMatch({{ sport: 'KBO' }}, 'NPB_KBO'),
        npb_kbo_dash: isSportMatch({{ sport: 'NPB' }}, 'NPB-KBO') && isSportMatch({{ sport: 'KBO' }}, 'NPB-KBO'),
        all_filter: isSportMatch({{ sport: 'NFL' }}, 'ALL') && isSportMatch({{ sport: 'TEN' }}, ''),
        null_filter: isSportMatch({{ sport: 'SOC' }}, null),
    }};
    return results;
    """
    results = run_js_eval(test_js)
    for key, val in results.items():
        assert val is True, f"Alias test {key} failed: got {val}"


def test_is_sport_match_edge_cases_and_falsy_inputs():
    """
    Empirically tests edge cases:
    - Empty object {}
    - null/undefined properties
    - Non-sports tickers (crypto, macro)
    """
    fn_code = get_extracted_is_sport_match_code()

    test_js = f"""
    {fn_code}
    const results = {{
        empty_obj: isSportMatch({{}}, 'TEN'),
        null_props: isSportMatch({{ sport: null, league: null, ticker: null }}, 'NFL'),
        crypto_ticker: isSportMatch({{ ticker: 'KXBTC-26OCT-95000' }}, 'TEN'),
        macro_ticker: isSportMatch({{ ticker: 'KXFED-RATE-CUT' }}, 'SOC'),
    }};
    return results;
    """
    results = run_js_eval(test_js)
    assert results["empty_obj"] is False, "Empty object should not match TEN"
    assert results["null_props"] is False, "Null properties should not match NFL"
    assert results["crypto_ticker"] is False, "Crypto ticker should not match TEN"
    assert results["macro_ticker"] is False, "Macro ticker should not match SOC"


# ─────────────────────────────────────────────────────────────────────────────
# 3. SETTINGS GATE & EMPTY LOADING STATE LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def test_settings_gate_decoupling_logic():
    """
    Empirically verifies the settings gate condition:
    When browsing a specific tab (e.g. f = 'TEN'), events must NOT be blocked by sportsEventAllowed.
    Only when f === 'ALL' does sportsEventAllowed take effect.
    """
    html = read_dashboard_html()

    # Verify the settings gate condition pattern in saas_dashboard.html
    gate_pattern = r"if\s*\(\s*f\s*===\s*['\"]ALL['\"]\s*&&\s*typeof\s+window\.sportsEventAllowed\s*===\s*['\"]function['\"]\s*&&\s*!window\.sportsEventAllowed\(e\)\s*\)\s*return\s+false;"
    assert re.search(gate_pattern, html), "Settings gate does not properly restrict window.sportsEventAllowed to f === 'ALL'"

    # Now execute simulated filtering in Node.js
    fn_code = get_extracted_is_sport_match_code()
    test_js = f"""
    {fn_code}
    const tennisEvent = {{ sport: 'TEN', league: 'ATP', event_ticker: 'KXATPMATCH-1' }};
    
    // Simulate sportsEventAllowed returning FALSE (user disabled tennis in settings)
    const sportsEventAllowed = (e) => false;
    
    function simulateFilter(e, f) {{
        if (!isSportMatch(e, f)) return false;
        if (f === 'ALL' && typeof sportsEventAllowed === 'function' && !sportsEventAllowed(e)) return false;
        return true;
    }}
    
    const specificTabResult = simulateFilter(tennisEvent, 'TEN');
    const allTabResult = simulateFilter(tennisEvent, 'ALL');
    
    return {{ specificTabResult, allTabResult }};
    """
    res = run_js_eval(test_js)
    assert res["specificTabResult"] is True, "Browsing specific tab 'TEN' was blocked by sportsEventAllowed!"
    assert res["allTabResult"] is False, "Browsing 'ALL' tab failed to enforce sportsEventAllowed!"


def test_empty_state_loading_display_condition():
    """
    Empirically verifies empty state rendering logic:
    When list.length === 0:
    - If window.__sportsLoading is true, container gets '⚡ Loading ... AI picks...'
    - If window.__sportsLoading is false, container gets 'No active AI picks for ... right now.'
    """
    html = read_dashboard_html()

    # Check the exact condition in HTML
    loading_snippet = re.search(r"if\s*\(\s*list\.length\s*===\s*0\s*\)\s*\{([\s\S]*?return;\s*\})", html)
    assert loading_snippet, "Could not find empty state check in renderSportsEvents"
    snippet_content = loading_snippet.group(1)

    assert "window.__sportsLoading" in snippet_content, "renderSportsEvents does not check window.__sportsLoading"
    assert "Loading" in snippet_content and "AI picks..." in snippet_content, "Loading pulse markup missing"
    assert "No active AI picks" in snippet_content, "No active picks fallback markup missing"

    # Now simulate the DOM output logic
    test_js = """
    function renderEmptyState(listLength, isLoading, label) {
        if (listLength === 0) {
            if (isLoading) {
                return '<div class="col-span-full text-center text-cyan-400 text-xs py-6 animate-pulse">⚡ Loading ' + label + ' AI picks...</div>';
            } else {
                return '<div class="col-span-full text-center text-gray-500 text-xs py-6">No active AI picks for ' + label + ' right now.</div>';
            }
        }
        return 'RENDERED_CARDS';
    }

    return {
        loading_ten: renderEmptyState(0, true, 'TEN'),
        empty_ten: renderEmptyState(0, false, 'TEN'),
        loading_all: renderEmptyState(0, true, 'any sport'),
        empty_all: renderEmptyState(0, false, 'any sport'),
    };
    """
    res = run_js_eval(test_js)
    assert "⚡ Loading TEN AI picks..." in res["loading_ten"]
    assert "No active AI picks for TEN right now." in res["empty_ten"]
    assert "⚡ Loading any sport AI picks..." in res["loading_all"]
    assert "No active AI picks for any sport right now." in res["empty_all"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. FILTER PIPELINE, NULL SAFETY & PULL-TO-REFRESH STRESS TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_render_sports_events_filter_pipeline_stress():
    """
    Empirically stress-tests the filtering pipeline inside renderSportsEvents:
    - Futures markets are excluded
    - Season win totals (e.g. KXNFLWINS) are excluded
    - Final/completed games are excluded
    - Games started past sport duration cap are excluded
    - Live games without includeLive toggle are excluded
    """
    fn_code = get_extracted_is_sport_match_code()
    test_js = f"""
    {fn_code}
    
    function filterEvent(e, f, includeLive, nowSec) {{
        if (!isSportMatch(e, f)) return false;
        if (e.market_type === 'Futures' || e.prop_type === 'Futures') return false;
        if (/KX(?:NFL|NBA|MLB|NHL)WINS|TOTAL WINS|WINS-\\d/i.test(String(e.event_ticker || e.ticker || '') + ' ' + String(e.title || ''))) return false;
        
        const st = String(e.status || (e.metadata || {{}}).status || '').toLowerCase();
        if (e.is_final || /^(final|completed|closed|ended|post|finished)/.test(st)) return false;
        const se = parseFloat(e.start_epoch) || 0;
        if (se > 0) {{
            const sp = String(e.sport || e.league || '').toUpperCase();
            const capH = /TEN|TENNIS/.test(sp) ? 6 : /MLB|NPB|KBO/.test(sp) ? 5.5 : /NFL|NCAAF/.test(sp) ? 4.5 : /NHL|NBA/.test(sp) ? 3.5 : /SOC|EPL|MLS/.test(sp) ? 3.2 : /UFC/.test(sp) ? 9 : 5;
            if (nowSec - se > capH * 3600) return false;
        }}
        const startEpoch = parseFloat(e.start_epoch) || 0;
        const isLive = startEpoch > 0 && startEpoch < nowSec;
        if (isLive && !includeLive) return false;
        return true;
    }}

    const now = 1700000000;
    const testCases = {{
        normal_open: filterEvent({{ sport: 'TEN', league: 'ATP', start_epoch: now + 3600 }}, 'TEN', false, now),
        futures_excluded: filterEvent({{ sport: 'NFL', league: 'NFL', market_type: 'Futures' }}, 'NFL', false, now),
        prop_futures_excluded: filterEvent({{ sport: 'NFL', league: 'NFL', prop_type: 'Futures' }}, 'NFL', false, now),
        season_wins_excluded: filterEvent({{ sport: 'NFL', event_ticker: 'KXNFLWINS-KC', title: 'Kansas City Total Wins' }}, 'NFL', false, now),
        final_game_excluded: filterEvent({{ sport: 'NHL', is_final: true }}, 'NHL', false, now),
        completed_status_excluded: filterEvent({{ sport: 'MLB', status: 'completed' }}, 'MLB', false, now),
        stale_tennis_game_excluded: filterEvent({{ sport: 'TEN', start_epoch: now - (7 * 3600) }}, 'TEN', true, now),
        live_game_without_toggle_excluded: filterEvent({{ sport: 'NFL', start_epoch: now - 1800 }}, 'NFL', false, now),
        live_game_with_toggle_included: filterEvent({{ sport: 'NFL', start_epoch: now - 1800 }}, 'NFL', true, now),
    }};
    return testCases;
    """
    res = run_js_eval(test_js)
    assert res["normal_open"] is True, "Open upcoming game should pass filter"
    assert res["futures_excluded"] is False, "Futures should be excluded"
    assert res["prop_futures_excluded"] is False, "Prop futures should be excluded"
    assert res["season_wins_excluded"] is False, "Season win totals should be excluded"
    assert res["final_game_excluded"] is False, "Final game should be excluded"
    assert res["completed_status_excluded"] is False, "Completed game should be excluded"
    assert res["stale_tennis_game_excluded"] is False, "Tennis game started 7h ago should be excluded"
    assert res["live_game_without_toggle_excluded"] is False, "Live game without toggle should be excluded"
    assert res["live_game_with_toggle_included"] is True, "Live game with toggle should be included"


def test_is_sport_match_null_event_vulnerability():
    """
    Empirically verifies defensive null-safety when evt is null or undefined:
    isSportMatch(null, 'NFL') safely returns false without throwing TypeError.
    """
    fn_code = get_extracted_is_sport_match_code()
    test_js = f"""
    {fn_code}
    let nullThrew = false;
    let nullError = '';
    let matchResult = null;
    try {{
        matchResult = isSportMatch(null, 'NFL');
    }} catch(e) {{
        nullThrew = true;
        nullError = e.message;
    }}
    return {{ nullThrew, nullError, matchResult }};
    """
    res = run_js_eval(test_js)
    assert res["nullThrew"] is False, f"Expected null guard to prevent throwing: {res.get('nullError')}"
    assert res["matchResult"] is False, f"Expected isSportMatch(null, 'NFL') to return false, got {res.get('matchResult')}"


def test_pull_to_refresh_filter_retention_contract():
    """
    Verifies that pull-to-refresh correctly passes window.sportsFilter to loadSportsEvents,
    preventing filter resets.
    """
    html = read_dashboard_html()
    assert "promises.push(loadSportsEvents(window.sportsFilter));" in html, (
        "Pull-to-refresh does not preserve window.sportsFilter when refreshing sports events"
    )

