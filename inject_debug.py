import re
with open('backend/routes/engine.py', 'r') as f:
    content = f.read()

replacement = '''                ev_date, start_epoch = extract_sports_event_date_and_time(
                    event_ticker, 
                    metadata=p_md, 
                    event_obj=e, 
                    slate_time_str=slate_time_str
                )
                if event_ticker == 'KXMLBGAME-26OCT081700CLECWS':
                    print(f"DEBUG MLB: slate_time_str={slate_time_str}, p_md={p_md}, ev_date={ev_date}, start_epoch={start_epoch}")'''

content = content.replace('''                ev_date, start_epoch = extract_sports_event_date_and_time(
                    event_ticker, 
                    metadata=p_md, 
                    event_obj=e, 
                    slate_time_str=slate_time_str
                )''', replacement)

with open('backend/routes/engine.py', 'w') as f:
    f.write(content)

print("Injected DEBUG print.")
