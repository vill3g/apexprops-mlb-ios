from PIL import Image

# Source generated image
src_path = r'C:\Users\Vill3\.gemini\antigravity\brain\f9732238-5384-4f24-8075-ded12557e9eb\text_icon_v2_1790829524592.jpg'
try:
    img = Image.open(src_path).convert('RGBA')
except Exception as e:
    print(f"Error opening image: {e}")
    exit(1)

# Function to resize and save
def save_icon(size, filename):
    resized = img.resize((size, size), Image.Resampling.LANCZOS)
    resized.save(filename)

# Save all required sizes
save_icon(512, r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\assets\app_icon_512.png')
save_icon(192, r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\assets\app_icon_192.png')
save_icon(180, r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\assets\apple-touch-icon.png')
save_icon(64, r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\favicon.ico')

print('Wordmark icons generated successfully.')
