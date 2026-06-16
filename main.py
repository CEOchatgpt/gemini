from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import yt_dlp
import subprocess
import os
import re
import tempfile
import requests
import time

app = FastAPI(title="Instagram Downloader API")

# کوکی‌ها از محیط
COOKIES_CONTENT = os.getenv("INSTAGRAM_COOKIES", "")
COOKIES_FILE = None

def get_cookies_file():
    global COOKIES_FILE
    if COOKIES_FILE is None and COOKIES_CONTENT:
        fd, path = tempfile.mkstemp(suffix=".txt", text=True)
        with os.fdopen(fd, 'w') as f:
            f.write(COOKIES_CONTENT)
        COOKIES_FILE = path
    return COOKIES_FILE

def download_media_with_gallery_dl(url):
    """دانلود فایل با gallery-dl و برگرداندن مسیر فایل"""
    try:
        cmd = ["gallery-dl", "-D", "/tmp", url]
        cookies_path = get_cookies_file()
        if cookies_path:
            cmd.insert(1, "--cookies")
            cmd.insert(2, cookies_path)
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
        
        # پیدا کردن فایل دانلود شده
        files = os.listdir("/tmp")
        for f in files:
            if f.endswith(('.mp4', '.jpg', '.jpeg', '.png')):
                return os.path.join("/tmp", f)
        return None
    except Exception as e:
        print(f"gallery-dl error: {e}")
        return None

def download_media_with_yt_dlp(url):
    """دانلود فایل با yt-dlp"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': '/tmp/%(id)s.%(ext)s',
            'cookiefile': get_cookies_file() if get_cookies_file() else None,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                # پیدا کردن فایل دانلود شده
                files = os.listdir("/tmp")
                for f in files:
                    if f.endswith(('.mp4', '.mkv', '.webm')):
                        return os.path.join("/tmp", f)
        return None
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return None

def upload_to_telegram(file_path, chat_id, bot_token, caption=""):
    """آپلود فایل به تلگرام"""
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    with open(file_path, 'rb') as f:
        files = {'document': f}
        data = {'chat_id': chat_id, 'caption': caption}
        response = requests.post(url, files=files, data=data)
    return response.json()

@app.get("/download")
async def download_and_send(
    url: str = Query(..., description="Instagram URL"),
    chat_id: int = Query(..., description="Telegram chat ID"),
    bot_token: str = Query(..., description="Telegram bot token")
):
    # مرحله ۱: دانلود فایل
    file_path = None
    
    # اولویت با gallery-dl
    if "/reel/" not in url.lower():
        file_path = download_media_with_gallery_dl(url)
    
    # اگر نشد، yt-dlp
    if not file_path:
        file_path = download_media_with_yt_dlp(url)
    
    if not file_path:
        raise HTTPException(status_code=404, detail="Could not download media")
    
    # مرحله ۲: آپلود به تلگرام
    result = upload_to_telegram(file_path, chat_id, bot_token, "📥 Downloaded from Instagram")
    
    # پاک کردن فایل
    try:
        os.remove(file_path)
    except:
        pass
    
    if result.get('ok'):
        return JSONResponse(content={
            "success": True,
            "message_id": result['result']['message_id']
        })
    else:
        raise HTTPException(status_code=500, detail="Telegram upload failed")
