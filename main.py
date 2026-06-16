from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import yt_dlp
import subprocess
import json
import os

app = FastAPI(title="Instagram Hybrid Scraper")

def scrape_with_gallery_dl(url: str):
    """
    استخراج لینک‌های عکس و آلبوم با استفاده از gallery-dl به صورت ایمن
    """
    try:
        # اجرای دستور برای گرفتن اطلاعات خام جی‌سون به صورت خط به خط
        result = subprocess.run(
            ["gallery-dl", "-j", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        media_list = []
        raw_output = result.stdout.strip().split('\n')
        
        for line in raw_output:
            if not line:
                continue
            try:
                data = json.loads(line)
                # بررسی ساختار خروجی استاندارد gallery-dl
                if isinstance(data, list):
                    # معمولاً اندیس آخر یا اندیسی که حاوی لینک cdn اینستاست مورد نظر ماست
                    for item in data:
                        if isinstance(item, str) and (item.startswith("http://") or item.startswith("https://")):
                            if "instagram" in item or "cdninstagram" in item:
                                is_video = item.lower().split('?')[0].endswith(('.mp4', '.m4v', '.mov'))
                                # جلوگیری از افزودن لینک‌های تکراری یک اسلاید
                                if not any(m['url'] == item for m in media_list):
                                    media_list.append({
                                        "url": item,
                                        "is_video": is_video
                                    })
            except Exception:
                continue
                
        return media_list
    except subprocess.CalledProcessError as ce:
        print(f"gallery-dl CLI failed: {ce.stderr}")
        return []
    except Exception as e:
        print(f"gallery-dl general error: {str(e)}")
        return []

@app.get("/scrape")
async def scrape_instagram(url: str = Query(..., description="Instagram URL")):
    # ۱. اولویت با gallery-dl برای پست‌ها، استوری‌ها و آلبوم‌ها
    if "/p/" in url or "/stories/" in url:
        gallery_data = scrape_with_gallery_dl(url)
        if gallery_data:
            if len(gallery_data) == 1:
                return JSONResponse(content={"type": "single", "data": gallery_data[0]})
            else:
                return JSONResponse(content={"type": "album", "data": gallery_data})

    # ۲. سوییچ روی yt-dlp برای ریلز یا به عنوان لایه پشتیبان عکس‌ها
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
                raise HTTPException(status_code=404, detail="No info found via yt-dlp")
                
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
        print(f"yt-dlp Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Both scrapers failed to extract media.")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
