import os

file_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\auth\routes.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

upload_route = """
from fastapi import UploadFile, File
import shutil

@router.post("/profile/picture")
async def upload_profile_picture(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    from backend.database.models import get_db_connection, DATA_DIR
    
    PROFILES_DIR = os.path.join(DATA_DIR, "profiles")
    os.makedirs(PROFILES_DIR, exist_ok=True)
    
    # Save the file
    ext = os.path.splitext(file.filename)[1]
    if not ext:
        ext = ".jpg"
    filename = f"user_{current_user['id']}{ext}"
    filepath = os.path.join(PROFILES_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    url = f"/profiles/{filename}"
    
    # Update user in database
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET profile_pic = ? WHERE id = ?", (url, current_user['id']))
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"success": True, "url": url}
"""

if "/profile/picture" not in content:
    content += "\n" + upload_route + "\n"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Added profile picture route.")
else:
    print("Route already exists.")
