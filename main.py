from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import yt_dlp
import subprocess
import json
import os

app = FastAPI(title="Instagram Hybrid Scraper")

def scrape_with_gallery_dl(url: str):
    """
    استخراج ایمن لینک‌های عکس و ویدیو با gallery-dl
    """
    try:
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
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str) and (item.startswith("http://") or item.startswith("https://")):
                            if "instagram" in item or "cdninstagram" in item:
                                # تشخیص ویدیو بر اساس ساختار اکستنشن یا پارامترها
                                is_video = any(ext in item.lower().split('?')[0] for ext in ['.mp4', '.m4v', '.mov'])
                                if not any(m['url'] == item for m in media_list):
                                    media_list.append({
                                        "url": item,
                                        "is_video": is_video
                                    })
            except Exception:
                continue
        return media_list
    except Exception as e:
        print(f"gallery-dl failed: {str(e)}")
        return []

@app.get("/scrape")
async def scrape_instagram(url: str = Query(..., description="Instagram URL")):
    clean_url = url.split('?')[0]

    # اگر لینک ریلز نباشد، اولویت مطلق با gallery-dl است تا عکس‌ها و آلبوم‌ها بدون خطا استخراج شوند
    if "/reel/" not in url.lower() and "/reels/" not in url.lower():
        gallery_data = scrape_with_gallery_dl(url)
        if gallery_data:
            if len(gallery_data) == 1:
                return JSONResponse(content={"type": "single", "data": gallery_data[0]})
            else:
                return JSONResponse(content={"type": "album", "data": gallery_data})

    # لایه پردازش ریلز یا بک‌آپ پست‌ها با yt-dlp
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        'format': 'best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]/best/bestvideo+bestaudio',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            if not info:
                raise HTTPException(status_code=404, detail="No info found via yt-dlp")
                
            if info.get('_type') == 'playlist' or 'entries' in info:
                media_list = []
                for entry in info['entries']:
                    if entry:
                        media_list.append({
                            "url": entry.get('url'),
                            "is_video": entry.get('ext') == 'mp4' or entry.get('vcodec') != 'none' or 'video' in entry.get('format_id', '').lower()
                        })
                if media_list:
                    return JSONResponse(content={"type": "album", "data": media_list})
            
            media_url = info.get('url')
            if info.get('formats'):
                media_url = info['formats'][-1].get('url', media_url)
                
            is_video = info.get('ext') == 'mp4' or info.get('vcodec') != 'none' or 'video' in info.get('format_id', '').lower()
            
            return JSONResponse(content={
                "type": "single",
                "data": {"url": media_url, "is_video": is_video}
            })
                
    except Exception as e:
        print(f"yt-dlp error: {str(e)}")
        # شانس آخر برای لینک‌هایی که از فیلتر بالا رد شده بودند
        fallback_data = scrape_with_gallery_dl(url)
        if fallback_data:
            if len(fallback_data) == 1:
                return JSONResponse(content={"type": "single", "data": fallback_data[0]})
            else:
                return JSONResponse(content={"type": "album", "data": fallback_data})
                
        raise HTTPException(status_code=500, detail="Both scrapers failed to extract media.")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
