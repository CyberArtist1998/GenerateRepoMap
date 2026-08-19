from PIL import Image
import os

img_path = r"C:\Users\RedRain2077\Desktop\google_cats_screenshot.png"

if os.path.exists(img_path):
    img = Image.open(img_path)
    print(f"Image size: {img.size}")
    print(f"Mode: {img.mode}")
    print(f"Format: {img.format}")
else:
    print("File not found!")
