import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_toggle = '''        guest_id = _get_guest_id(request) if request else None
        res = get_auto_executor(asset, guest_id=guest_id).set_enabled(enabled)
        
        if guest_id:
            from backend.database.models import update_user_ai_enabled
            update_user_ai_enabled(guest_id, enabled)'''

new_toggle = '''        guest_id = _get_guest_id(request) if request else None
        user_id = getattr(request.state, "user_id", None) if request else None
        
        # Determine the target ID (SaaS user or Guest)
        target_id = user_id if user_id else guest_id
        
        res = get_auto_executor(asset, guest_id=target_id).set_enabled(enabled)
        
        if target_id:
            from backend.database.models import update_user_ai_enabled
            update_user_ai_enabled(target_id, enabled)'''

content = content.replace(old_toggle, new_toggle)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
