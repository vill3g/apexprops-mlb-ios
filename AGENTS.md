
---
description: Critical UI rules for iOS and PWA styling.
trigger: always_on
---

# UI Styling Rules
To prevent the iOS status bar blur and black gap issues:
1. NEVER use `viewport-fit=cover` in the viewport meta tag.
2. ALWAYS use `<meta name="apple-mobile-web-app-status-bar-style" content="black">`. DO NOT use `black-translucent` as it introduces a dark blur gradient over the header content.

