from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import yt_dlp
import subprocess
import json
import os

app = FastAPI(title="Instagram Hybrid Scraper")

def scrape_with_gallery_dl(url: str):
    """
    استخراج لینک‌های عکس و آلبوم با استفاده از gallery-dl
    """
    try:
        # اجرای دستور gallery-dl برای گرفتن خروجی به صورت جی‌سون بدون دانلود فایل
        result = subprocess.run(
            ["gallery-dl", "-j", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        # خروجی gallery-dl به صورت خط به خط جی‌سون آرایه‌ای است
        raw_output = result.stdout.strip().split('\n')
        media_list = []
        
        for line in raw_output:
            if not line:
                continue
            data = json.loads(line)
            # در خروجی نوع ۳ معمولاً لینک مستقیم فایل در اندیس ۲ قرار دارد
            if isinstance(data, list) and len(data) >= 3:
                file_url = data[2]
                # تشخیص اینکه فایل ویدیو است یا عکس بر اساس پسوند
                is_video = file_url.lower().endswith(('.mp4', '.m4v', '.mov'))
                media_list.append({
                    "url": file_url,
                    "is_video": is_video
                })
        
        return media_list
    except Exception as e:
        print(f"gallery-dl Error: {str(e)}")
        return []

@app.get("/scrape")
async def scrape_instagram(url: str = Query(..., description="Instagram URL")):
    # ۱. ابتدا شانس را به gallery-dl می‌دهیم چون کاروسل‌ها و عکس‌ها را عالی هندل می‌کند
    # اگر لینک پست عادی، کاروسل، استوری یا هایلایت باشد
    if "/p/" in url or "/stories/" in url:
        gallery_data = scrape_with_gallery_dl(url)
        if gallery_data:
            if len(gallery_data) == 1:
                return JSONResponse(content={"type": "single", "data": gallery_data[0]})
            else:
                return JSONResponse(content={"type": "album", "data": gallery_data})

    # ۲. اگر لینک ریلز بود یا gallery-dl نتوانست چیزی پیدا کند، سوییچ میکنیم روی yt-dlp
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        'format': 'best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]/best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise HTTPException(status_code=404, detail="No info found")
                
            if info.get('_type') == 'playlist' or 'entries' in info:
                media_list = []
                for entry in info['entries']:
                    if entry:
                        media_list.append({
                            "url": entry.get('url'),
                            "is_video": entry.get('ext') == 'mp4' or entry.get('vcodec') != 'none'
                        })
                return JSONResponse(content={"type": "album", "data": media_list})
            else:
                media_url = info.get('url')
                is_video = info.get('ext') == 'mp4' or info.get('vcodec') != 'none'
                return JSONResponse(content={
                    "type": "single",
                    "data": {"url": media_url, "is_video": is_video}
                })
                
    except Exception as e:
        print(f"yt-dlp Fallback Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"All scrapers failed: {str(e)}")
