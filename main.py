from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import yt_dlp
import os

app = FastAPI(title="Instagram Link Scraper")

# فایل main.py

@app.get("/scrape")
async def scrape_instagram(url: str = Query(..., description="Instagram post/reel/story URL")):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        # 🌟 اصلاح اصلی: انتخاب بهترین ویدیویی که خودش صدا دارد و فرمتش ترجیحاً mp4 است
        'format': 'best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]/best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }
    
    # بقیه کدهای تابع دست‌نخورده باقی می‌ماند، اما آن خط انتخاب فرمت [-1] را پاک کن یا به این شکل تغییر بده:
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
                # 🌟 استفاده از همان سورس اصلی که طبق فیلتر بالا بهترین فرمتِ باصدا انتخاب شده است
                media_url = info.get('url')
                is_video = info.get('ext') == 'mp4' or info.get('vcodec') != 'none'
                
                return JSONResponse(content={
                    "type": "single",
                    "data": {
                        "url": media_url,
                        "is_video": is_video
                    }
                })
    except Exception as e:
        # مدیریت خطا...
        print(f"yt-dlp Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # رندر پورت را داینامیک تعیین می‌کند
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
