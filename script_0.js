
    // ===== NULL-SAFE DOM HELPERS =====
    // Safely get element by ID; returns null without throwing if ID is missing from DOM.
    function safeEl(id) { return document.getElementById(id); }
    // Safely set a property (e.g. innerText) on an element; no-op if element is null.
    function safeSet(id, prop, val) { var el = document.getElementById(id); if (el) el[prop] = val; }
    // Safely set innerHTML; no-op if element is null.
    function safeHtml(id, html) { var el = document.getElementById(id); if (el) el.innerHTML = html; }
    // ===== END NULL-SAFE DOM HELPERS =====

    if (window.TradingView) {
      window.TradingView.getWidgetTitleAttribute = function() { return ""; };
    }
  