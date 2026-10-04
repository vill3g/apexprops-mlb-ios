
from PIL import Image

try:
    # Convert icon
    img = Image.open("assets/icon.png")
    img.save("assets/icon.png", "PNG")
    print("Icon converted")
except Exception as e:
    print(f"Icon error: {e}")

try:
    # Convert splash
    splash = Image.open("assets/splash.png")
    splash.save("assets/splash.png", "PNG")
    print("Splash converted")
except Exception as e:
    print(f"Splash error: {e}")

