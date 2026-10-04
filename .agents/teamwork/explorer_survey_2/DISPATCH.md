# Explorer Survey 2 Dispatch

You are explorer_survey_2.
Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_2
Project root: C:\Users\Vill3\Desktop\ShadowTraderAi
Mandatory reference: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\ORIGINAL_REQUEST.md

Mission: Survey the codebase with a focus on Frontend UI/UX and iOS Smoothness (R2).
Specifically investigate:
- `static/saas_dashboard.html` and any other HTML templates: check for unclosed HTML tags, structural HTML errors, invalid attributes.
- Frontend JavaScript files and embedded scripts: check for syntax errors, console errors, unhandled promise rejections, performance bottlenecks, expensive DOM queries or interval timers.
- CSS files and responsive styles: inspect iOS safe area styling (env(safe-area-inset-*)), viewport meta tags, overflow bugs, overlapping UI elements, mobile viewport scaling.
- Capacitor / iOS wrapper configurations: inspect capacitor.config.*, iOS project files if present, native bridge interactions.

Output:
Write a comprehensive report to `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_2\survey_report.md` and `handoff.md`.
Include:
- Exact file paths, line numbers, and architectural findings.
- Inventory of existing frontend/iOS issues/bugs found.
- Concrete recommendations for fixes and verification.
