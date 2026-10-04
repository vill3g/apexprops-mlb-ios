const fs = require('fs');
const vm = require('vm');

function auditHtmlScripts(filePath) {
    console.log(`\n========================================`);
    console.log(`Checking inline scripts in: ${filePath}`);
    console.log(`========================================`);
    if (!fs.existsSync(filePath)) {
        console.log("File not found!");
        return;
    }

    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n');
    
    // Regex for script tags
    const scriptRegex = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
    let match;
    let scriptIdx = 0;
    let errorCount = 0;

    while ((match = scriptRegex.exec(content)) !== null) {
        scriptIdx++;
        const attrs = match[1];
        const scriptCode = match[2];
        
        // Skip external scripts
        if (/src\s*=/i.test(attrs)) {
            continue;
        }

        // Calculate line number where script begins
        const offset = match.index;
        const lineNum = content.substring(0, offset).split('\n').length;

        try {
            new vm.Script(scriptCode, { filename: `${filePath}:inline_${scriptIdx}`, lineOffset: lineNum - 1 });
        } catch (err) {
            errorCount++;
            console.error(`Syntax error in script #${scriptIdx} at line ~${lineNum}:`);
            console.error(err.message);
            console.error(err.stack.split('\n').slice(0, 3).join('\n'));
        }
    }
    console.log(`Total inline scripts checked: ${scriptIdx}, Errors: ${errorCount}`);
}

['static/saas_dashboard.html', 'static/login.html', 'static/trades.html', 'static/admin_mobile.html'].forEach(auditHtmlScripts);
