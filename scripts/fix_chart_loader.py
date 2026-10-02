import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update hideChartLoader function to be robust and immediate
old_hide = """        function hideChartLoader() {
            const el = document.getElementById('chart-loader');
            if (el) { el.style.opacity='0'; setTimeout(()=>el.style.display='none',300); }
        }"""

new_hide = """        function hideChartLoader() {
            const el = document.getElementById('chart-loader');
            if (el) {
                el.style.opacity = '0';
                el.style.display = 'none';
                el.classList.add('pointer-events-none');
            }
        }"""

if old_hide in content:
    content = content.replace(old_hide, new_hide)
    print("Updated hideChartLoader")

# 2. Add isChartInitializing and ensure initChart clears duplicate containers and hides loader in finally
pattern_init_chart = r'async function initChart\(\) \{'
replacement_init_chart = """let isChartInitializing = false;
        async function initChart() {
            if (chartInitialized || isChartInitializing) return;
            isChartInitializing = true;"""

if "let isChartInitializing = false;" not in content:
    content = re.sub(pattern_init_chart, replacement_init_chart, content)
    print("Added isChartInitializing guard to initChart")

# Ensure lw-chart-container is cleaned before creating a new chart
clean_container_code = """            const container = document.getElementById('lw-chart-container');
            if (!container) { hideChartLoader(); isChartInitializing = false; return; }
            container.innerHTML = '';"""

content = re.sub(
    r'const container = document\.getElementById\(\'lw-chart-container\'\);\s*if \(!container\) \{ hideChartLoader\(\); return; \}',
    clean_container_code,
    content
)
print("Added container cleanup to prevent duplicate canvas stacking")

# Ensure finally block in initChart
old_catch_init = """            } catch(err) {
                console.error('[Chart] init error:', err);
                hideChartLoader();
            }
        }"""

new_catch_init = """                chartInitialized = true;
            } catch(err) {
                console.error('[Chart] init error:', err);
            } finally {
                isChartInitializing = false;
                hideChartLoader();
            }
        }"""

if old_catch_init in content:
    content = content.replace(old_catch_init, new_catch_init)
    print("Added finally block to initChart")

# 3. Update selectDashboardAsset to await fetchChartData and always hide loader
old_select_end = """            // Immediately fetch fresh chart and contract data
            if (typeof fetchChartData === 'function') fetchChartData();
            if (typeof fetchKalshiData === 'function') fetchKalshiData();
            if (typeof fetchLiveBids === 'function') fetchLiveBids();
        }"""

new_select_end = """            // Immediately fetch fresh chart and contract data
            try {
                if (typeof fetchChartData === 'function') await fetchChartData();
                if (typeof fetchKalshiData === 'function') fetchKalshiData();
                if (typeof fetchLiveBids === 'function') fetchLiveBids();
            } finally {
                hideChartLoader();
            }
        }"""

if old_select_end in content:
    content = content.replace(old_select_end, new_select_end)
    print("Updated selectDashboardAsset with await and finally hideChartLoader")

# Make selectDashboardAsset async if needed
content = content.replace(
    "function selectDashboardAsset(asset) {",
    "async function selectDashboardAsset(asset) {"
)

# 4. Make sure fetchChartData always calls hideChartLoader()
old_fetch_chart_end = """                if (d.volume?.length) volumeSeries.setData(d.volume);
            } catch(e) { console.warn('[Chart] fetch err', e); }
        }"""

new_fetch_chart_end = """                if (d.volume?.length && volumeSeries) volumeSeries.setData(d.volume);
            } catch(e) { console.warn('[Chart] fetch err', e); }
            finally {
                hideChartLoader();
            }
        }"""

if old_fetch_chart_end in content:
    content = content.replace(old_fetch_chart_end, new_fetch_chart_end)
    print("Added finally hideChartLoader to fetchChartData")

# 5. Remove duplicate initChart() call at bottom
content = content.replace("        initChart();\n        setTimeout(() => {", "        setTimeout(() => {")
print("Removed duplicate initChart() call")

# 6. Add a quick fallback timeout to guarantee chart-loader is hidden
content = content.replace(
    "setTimeout(() => {\n            const el = document.getElementById('chart-loader');\n            if (el) { el.style.display = 'none'; }\n        }, 5000);",
    "setTimeout(hideChartLoader, 2000);\n        setTimeout(hideChartLoader, 4000);"
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied successfully to saas_dashboard.html")
