file_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add uploadProfilePic function
js_upload = """
async function uploadProfilePic(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const res = await fetch('/api/auth/profile/picture', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + token },
            body: formData
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast("Profile picture updated!", "success");
            const avatar = document.getElementById('socialYourAvatar');
            if(avatar) {
                avatar.style.backgroundImage = `url(${data.url})`;
                avatar.innerHTML = "";
            }
        } else {
            showToast("Failed to upload: " + (data.detail || "Unknown error"), "error");
        }
    } catch (e) {
        showToast("Error uploading picture.", "error");
    }
}
"""

if "function uploadProfilePic" not in content:
    content += "\n" + js_upload
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Added uploadProfilePic")
else:
    print("uploadProfilePic already exists")

# Need to update checkAuth to load profile_pic
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

if "data.profile_pic" not in content:
    # Find checkAuth setting username
    content = content.replace("document.getElementById('socialYourUsername').textContent = data.username;", 
    """document.getElementById('socialYourUsername').textContent = data.username;
        if (data.profile_pic) {
            const avatar = document.getElementById('socialYourAvatar');
            if(avatar) {
                avatar.style.backgroundImage = `url(${data.profile_pic})`;
                avatar.innerHTML = '';
            }
        }""")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated checkAuth")
else:
    print("checkAuth already updated")
