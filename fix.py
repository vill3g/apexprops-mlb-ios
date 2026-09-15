def fix():
    with open('static/index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''        if (banner) {
          banner.style.background = "rgba(245, 158, 11, 0.10)";
          banner.style.borderColor = "#f59e0b";
        }
        return;'''

    injection = '''        if (banner) {
          banner.style.background = "rgba(245, 158, 11, 0.10)";
          banner.style.borderColor = "#f59e0b";
        }
        const bubble = document.getElementById("kalshiMLStatusBubble");
        if (bubble) {
          bubble.innerText = `SCANNING (${Math.max(0, 30 - elapsed)}s)`;
          bubble.className = "ml-1 px-1.5 py-0.5 text-[8px] font-bold uppercase rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/50 animate-pulse whitespace-nowrap";
        }
        return;'''

    content = content.replace(target, injection)

    with open('static/index.html', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix()
    print("Fixed via python script!")
