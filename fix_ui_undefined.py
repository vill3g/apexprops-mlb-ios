with open('static/js/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace:
old_code = '''
              if (kYes) kYes.innerText = ${liveData.kalshi.yes_prob}% Yes (Above);
              if (kNo) kNo.innerText = ${liveData.kalshi.no_prob}% No (Below);
              if (btnProbAbove) btnProbAbove.innerText = ${liveData.kalshi.yes_prob}%;
              if (btnProbBelow) btnProbBelow.innerText = ${liveData.kalshi.no_prob}%;
'''
new_code = '''
              if (liveData.kalshi.yes_prob !== undefined) {
                  if (kYes) kYes.innerText = ${liveData.kalshi.yes_prob}% Yes (Above);
                  if (btnProbAbove) btnProbAbove.innerText = ${liveData.kalshi.yes_prob}%;
              }
              if (liveData.kalshi.no_prob !== undefined) {
                  if (kNo) kNo.innerText = ${liveData.kalshi.no_prob}% No (Below);
                  if (btnProbBelow) btnProbBelow.innerText = ${liveData.kalshi.no_prob}%;
              }
'''
content = content.replace(old_code.strip(), new_code.strip())

with open('static/js/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
