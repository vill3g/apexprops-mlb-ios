with open('scratch.html', encoding='utf-8') as f: content = f.read()
html = f"""<!DOCTYPE html>
<html lang="en" class="bg-slate-950 text-white h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Kalshi Admin Console</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; }}
        ::-webkit-scrollbar {{ display: none; }}
    </style>
</head>
<body class="flex flex-col h-full overflow-hidden bg-slate-950 m-0 p-0">
    {content}
    <script>
        window.token = localStorage.getItem('saas_token') || localStorage.getItem('kalshi_token');
        function getAuthHeaders(headers = {{}}) {{
            return {{
                'Authorization': 'Bearer ' + window.token,
                'Content-Type': 'application/json',
                ...headers
            }};
        }}
        function getKalshiApiBase() {{ return ''; }}
        window.getAuthHeaders = getAuthHeaders;
        window.getKalshiApiBase = getKalshiApiBase;
        window.showAppToast = function(title, body, color) {{ alert(title + ': ' + body); }};
        
        document.addEventListener('DOMContentLoaded', () => {{
            const modal = document.getElementById('adminUserModal');
            if (modal) {{
                modal.classList.remove('hidden', 'bg-black/80', 'fixed', 'inset-0', 'p-4', 'z-[100]', 'items-center', 'justify-center', 'backdrop-blur-sm');
                modal.className += ' flex flex-col flex-1 w-full h-full';
                const inner = modal.firstElementChild;
                if(inner) {{
                    inner.classList.remove('max-w-6xl', 'h-[90vh]', 'rounded-2xl', 'border');
                    inner.className += ' flex flex-col flex-1 w-full h-full rounded-none border-0';
                }}
                const closeBtn = document.querySelector('button[title="Close Panel"]');
                if (closeBtn) closeBtn.style.display = 'none';
            }}
        }});
    </script>
    <script src="/static/js/admin_users.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            setTimeout(() => {{
                if (window.openAdminUserPanel) {{
                    window.openAdminUserPanel();
                }}
            }}, 100);
        }});
    </script>
</body>
</html>"""
with open('static/admin_mobile.html', 'w', encoding='utf-8') as f:
    f.write(html)
