const trades = [
    { trading_style: "SECOND_ENTRY", is_second_entry: false },
    { trading_style: "AUTO", is_second_entry: true }
];

trades.forEach(t => {
    let badges = [];
    const exitReason = String(t.exit_reason || "").toUpperCase();
    const isManual = t.is_manual === true || (exitReason === "MANUAL" && !t.trading_style);

    if (isManual) {
        badges.push('<span class="MANUAL">MANUAL</span>');
    } else {
        let styleStr = (t.trading_style && t.trading_style !== "REVERSAL") ? String(t.trading_style).replace(/_/g, ' ') : "🤖 AUTO";
        if (styleStr.includes("SECOND ENTRY") || styleStr.includes("THIRD ENTRY") || styleStr.includes("STOP LOSS REENTRY") || styleStr.includes("REENTRY")) {
            styleStr = "🤖 AUTO";
        }
        badges.push('<span class="STYLE">' + styleStr + '</span>');
    }
    
    const ts = t.trading_style || "";
    if (t.is_profit_reentry || t.is_second_entry || t.is_third_entry || t.is_stop_loss_reentry || ts.includes('SECOND_ENTRY') || ts.includes('THIRD_ENTRY') || ts.includes('STOP_LOSS_REENTRY') || (t.reason && (t.reason.includes('SECOND_ENTRY') || t.reason.includes('THIRD_ENTRY') || t.reason.includes('STOP_LOSS_REENTRY')))) {
        const isThird = (ts === 'THIRD_ENTRY' || t.is_third_entry || (t.reason && t.reason.includes('THIRD_ENTRY')));
        const isSL = (t.is_stop_loss_reentry || (t.reason && t.reason.includes('STOP_LOSS_REENTRY')));
        const baseText = isThird ? '3RD ENTRY' : '2ND ENTRY';
        const reentryText = isSL ? ('DIP RE-ENTRY (' + baseText + ')') : baseText;
        badges.push('<span class="REENTRY">' + reentryText + '</span>');
    }
    
    console.log("Trade:", t);
    console.log("Badges:", badges);
});
