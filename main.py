from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import yt_dlp
from typing import Optional, List
import os
import tempfile
import subprocess
import uuid
import asyncio
from pathlib import Path
import re

app = FastAPI(title="AnyStreamPro API", version="2.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temp directory for downloads
TEMP_DIR = Path(tempfile.gettempdir()) / "anystreampro"
TEMP_DIR.mkdir(exist_ok=True)

class URLRequest(BaseModel):
    url: str
    proxy: Optional[str] = None

class DownloadRequest(BaseModel):
    url: str
    video_format: str
    audio_format: str
    proxy: Optional[str] = None

class FormatInfo(BaseModel):
    format_id: str
    ext: str
    resolution: str
    note: str
    type: str
    filesize: Optional[int]
    height: int

class FormatsResponse(BaseModel):
    status: str
    title: str
    thumbnail: str
    formats: List[FormatInfo]

def sanitize_filename(name: str) -> str:
    """Remove invalid characters from filename"""
    return re.sub(r'[<>:"/\\|?*]', '', name)[:200]

def cleanup_old_files():
    """Remove files older than 1 hour"""
    import time
    now = time.time()
    for f in TEMP_DIR.glob("*"):
        if f.is_file() and (now - f.stat().st_mtime) > 3600:
            try:
                f.unlink()
            except:
                pass

@app.get("/")
async def root():
    return {"message": "AnyStreamPro API v2", "status": "online", "features": ["merge"]}

@app.get("/health")
async def health():
    # Check if ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        ffmpeg_status = "available"
    except:
        ffmpeg_status = "not found"
    return {"status": "healthy", "ffmpeg": ffmpeg_status}

@app.post("/api/formats", response_model=FormatsResponse)
async def get_formats(request: URLRequest):
    """Extract available formats from a video URL"""
    cleanup_old_files()

    print(f"DEBUG: Processing URL: {request.url}")

    # Handle cookies from env
    cookie_file = None
    if os.environ.get('COOKIES_CONTENT'):
        cookie_path = TEMP_DIR / "cookies.txt"
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(os.environ['COOKIES_CONTENT'])
        cookie_file = str(cookie_path)
    elif os.path.exists("cookies.txt"):
        print("DEBUG: Found local cookies.txt file")
        cookie_file = "cookies.txt"

    # Use default robust options instead of forcing clients
    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
        'skip_download': True,
        'proxy': request.proxy if request.proxy else None,
        'cookiefile': cookie_file,
        'logtostderr': True,
        # 'format': 'best', # Un-commenting this sometimes helps, but default is usually fine for metadata
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"DEBUG: Extracting info for {request.url}")
            info = ydl.extract_info(request.url, download=False)

            title = info.get('title', 'Unknown Title')
            thumbnail = info.get('thumbnail')
            if not thumbnail and info.get('thumbnails'):
                thumbnails = info.get('thumbnails', [])
                if thumbnails:
                    # Get highest resolution thumbnail
                    thumbnail = thumbnails[-1].get('url')

            formats = []
            raw_formats = info.get('formats', [])

            if not raw_formats:
                # Some sites (like instagram) might not return 'formats' but just a direct url
                if info.get('url'):
                    # Create a synthetic format
                    formats.append(FormatInfo(
                        format_id='default',
                        ext=info.get('ext', 'mp4'),
                        resolution=f"{info.get('width', '?')}x{info.get('height', '?')}",
                        note='Default Source',
                        type='combined',
                        filesize=info.get('filesize'),
                        height=info.get('height', 0),
                    ))

            for f in raw_formats:
                vcodec = f.get('vcodec')
                acodec = f.get('acodec')
                height = f.get('height') or 0

                has_video = vcodec and vcodec != 'none'
                has_audio = acodec and acodec != 'none'

                if has_video and not has_audio:
                    type_label = "video"
                elif has_audio and not has_video:
                    type_label = "audio"
                elif has_video and has_audio:
                    type_label = "combined"
                else:
                    continue

                bitrate = f.get('tbr')
                note = f.get('format_note', '')
                if bitrate:
                    note = f"{note} ({int(bitrate)}kbps)".strip()

                formats.append(FormatInfo(
                    format_id=f['format_id'],
                    ext=f.get('ext', ''),
                    resolution=f.get('resolution') or f"{f.get('width','?')}x{height}",
                    note=note,
                    type=type_label,
                    filesize=f.get('filesize'),
                    height=height,
                ))

            formats.sort(key=lambda x: x.height, reverse=True)

            print(f"DEBUG: Successfully found {len(formats)} formats")
            return FormatsResponse(
                status="success",
                title=title,
                thumbnail=thumbnail or '',
                formats=formats
            )

    except Exception as e:
        error_msg = str(e)
        print(f"DEBUG: Extraction failed: {error_msg}")
        raise HTTPException(status_code=400, detail=f"Extraction failed: {error_msg}")

@app.post("/api/download")
async def download_merged(request: DownloadRequest):
    """Download and merge video+audio, then stream to user"""

    job_id = str(uuid.uuid4())[:8]
    video_file = TEMP_DIR / f"{job_id}_video.mp4"
    audio_file = TEMP_DIR / f"{job_id}_audio.m4a"
    output_file = TEMP_DIR / f"{job_id}_merged.mp4"

    # Handle cookies from env
    cookie_file = None
    if os.environ.get('COOKIES_CONTENT'):
        cookie_path = TEMP_DIR / "cookies.txt"
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(os.environ['COOKIES_CONTENT'])
        cookie_file = str(cookie_path)

    try:
        # Get video info first for title
        ydl_opts_info = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'proxy': request.proxy if request.proxy else None,
            'cookiefile': cookie_file,
        }

        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(request.url, download=False)
            title = sanitize_filename(info.get('title', 'video'))

        # Download video stream
        ydl_opts_video = {
            'format': request.video_format,
            'quiet': True,
            'no_warnings': True,
            'outtmpl': str(video_file),
            'proxy': request.proxy if request.proxy else None,
            'cookiefile': cookie_file,
        }

        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            ydl.download([request.url])

        # Download audio stream
        ydl_opts_audio = {
            'format': request.audio_format,
            'quiet': True,
            'no_warnings': True,
            'outtmpl': str(audio_file),
            'proxy': request.proxy if request.proxy else None,
            'cookiefile': cookie_file,
        }

        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            ydl.download([request.url])

        # Merge with ffmpeg
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-i', str(video_file),
            '-i', str(audio_file),
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-strict', 'experimental',
            str(output_file)
        ]

        process = subprocess.run(ffmpeg_cmd, capture_output=True)
        if process.returncode != 0:
            raise Exception(f"FFmpeg failed: {process.stderr.decode()}")

        # Cleanup temp files
        if video_file.exists():
            video_file.unlink()
        if audio_file.exists():
            audio_file.unlink()

        # Return file with proper name
        filename = f"{title}.mp4"

        def file_iterator():
            with open(output_file, 'rb') as f:
                while chunk := f.read(1024 * 1024):  # 1MB chunks
                    yield chunk
            # Cleanup after sending
            try:
                output_file.unlink()
            except:
                pass

        return StreamingResponse(
            file_iterator(),
            media_type='video/mp4',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'video/mp4',
            }
        )

    except Exception as e:
        # Cleanup on error
        for f in [video_file, audio_file, output_file]:
            if f.exists():
                try:
                    f.unlink()
                except:
                    pass
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
