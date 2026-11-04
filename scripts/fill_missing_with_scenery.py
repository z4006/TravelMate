"""为缺图景点补充通用风景照（只处理抓图失败的记录）。

思路：
1. 先从 Bing 图片搜索抓一批风景照片，做质量校验后存成 scenery-XX.jpg；
2. 只有 data/image-cache 中不存在或为空（抓取失败）的景点才替换；
3. 结果按 id 取模分配，保证稳定。

校验规则（过滤地图、截图、单调图）：
- 必须是横向构图（宽 >= 1.25 * 高）
- 宽度 >= 600
- 三个颜色通道的标准差均值 >= 25（地图/白底图会被过滤）

用法（服务器，root）：
    TRAVELMATE_DATABASE=/var/lib/travelmate/travelmate.db \
        /opt/travelmate/.venv/bin/python -m scripts.fill_missing_with_scenery
"""

import argparse
import hashlib
import html as html_module
import io
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "static" / "images" / "attractions"
THUMB_DIR = IMG_DIR / "thumbs"
CACHE_DIR = ROOT / "data" / "image-cache"

TIMEOUT = 10
POOL_SIZE = 40
MAX_WIDTH = 800
THUMB_WIDTH = 360
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# 只接受这些图源（壁纸站与免费图库，通常无水印）
ALLOWED_HOSTS = (
    "wallpaperaccess",
    "wallpapersafari",
    "unsplash",
    "pexels",
    "pixabay",
    "flickr",
    "wikimedia",
    "pxhere",
    "publicdomainpictures",
)

# 明确拒绝的图库/水印站
BLOCKED_HOSTS = (
    "nipic",
    "588ku",
    "699pic",
    "veer",
    "zcool",
    "photophoto",
    "qiantu",
    "hc360",
    "2008php",
    "oceanld",
    "gei6",
    "51jiaoxi",
    "quword",
    "duitang",
    "sinaimg",
    "baidu",
    "zhimg",
    "pinterest",
)

QUERIES = (
    "mountain lake landscape wallpaper",
    "sunset beach landscape wallpaper",
    "forest morning mist landscape wallpaper",
    "ancient town china landscape wallpaper",
    "grassland scenery wallpaper",
    "autumn mountain landscape wallpaper",
    "nature wallpaper 4k mountains",
    "desert dunes landscape wallpaper",
    "waterfall jungle landscape wallpaper",
    "snow mountain landscape wallpaper",
    "rice terrace landscape wallpaper",
    "river valley landscape wallpaper",
    "spring blossom landscape wallpaper",
    "ocean cliff landscape wallpaper",
    "starry night landscape wallpaper",
    "cherry blossom lake wallpaper",
    "canyon landscape wallpaper",
    "lavender field wallpaper",
    "tropical island wallpaper",
    "misty forest wallpaper",
)


def _safe_url(url: str) -> str:
    return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%")


def _download(url: str, timeout: int = TIMEOUT) -> bytes | None:
    try:
        request = urllib.request.Request(
            _safe_url(url),
            headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def _host_ok(url: str) -> bool:
    import urllib.parse as _u

    host = _u.urlparse(url).netloc.lower()
    if any(bad in host for bad in BLOCKED_HOSTS):
        return False
    if any(good in host for good in ALLOWED_HOSTS):
        return True
    return False  # 默认拒绝，保证只用品质可控的图源


def _bing_images(query: str, limit: int = 25) -> list[str]:
    url = "https://cn.bing.com/images/search?q=" + urllib.parse.quote(query)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            page = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return []
    found = re.findall(r"murl&quot;:&quot;(https?://[^&]+)", page)
    urls = []
    for raw in found:
        candidate = html_module.unescape(urllib.parse.unquote(raw))
        if not candidate.startswith("http") or candidate in urls:
            continue
        if not _host_ok(candidate):
            continue
        urls.append(candidate)
        if len(urls) >= limit:
            break
    return urls


def _looks_like_photo(image) -> bool:
    from PIL import ImageStat

    if image.width < 600 or image.width < image.height * 1.25:
        return False
    stat = ImageStat.Stat(image.convert("RGB"))
    return sum(stat.stddev) / 3 >= 25


def _save(image_bytes: bytes, filename: str) -> bool:
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return False
    if not _looks_like_photo(image):
        return False

    if image.width > MAX_WIDTH:
        ratio = MAX_WIDTH / image.width
        image = image.resize((MAX_WIDTH, int(image.height * ratio)), Image.LANCZOS)

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    image.save(IMG_DIR / filename, "JPEG", quality=82, optimize=True)

    thumb = image.copy()
    if thumb.width > THUMB_WIDTH:
        ratio = THUMB_WIDTH / thumb.width
        thumb = thumb.resize((THUMB_WIDTH, int(thumb.height * ratio)), Image.LANCZOS)
    thumb.save(THUMB_DIR / filename, "JPEG", quality=72, optimize=True)
    return True


def build_pool() -> int:
    existing = sorted(IMG_DIR.glob("scenery-*.jpg"))
    count = len(existing)
    if count >= POOL_SIZE:
        return count

    for query in QUERIES:
        if count >= POOL_SIZE:
            break
        for candidate in _bing_images(query):
            if count >= POOL_SIZE:
                break
            payload = _download(candidate)
            if not payload:
                continue
            filename = f"scenery-{count + 1:02d}.jpg"
            if _save(payload, filename):
                count += 1
                print("  新增", filename, flush=True)
    return count


def _cache_path(src: str) -> Path:
    suffix = Path(urlparse(src).path).suffix.lower() or ".jpg"
    return CACHE_DIR / (hashlib.sha256(src.encode("utf-8")).hexdigest() + suffix)


def main() -> None:
    parser = argparse.ArgumentParser(description="为缺图景点补充风景照")
    parser.add_argument("--pool-only", action="store_true", help="只准备图池，不修改数据")
    args = parser.parse_args()

    print("准备风景图池…", flush=True)
    pool = build_pool()
    print("图池数量:", pool, flush=True)
    if pool == 0:
        raise SystemExit("没有可用的风景图")
    if args.pool_only:
        return

    from app import create_app
    from database.connection import db_transaction, get_db

    names = [f"/static/images/attractions/scenery-{i + 1:02d}.jpg" for i in range(pool)]

    app = create_app(init_database=False)
    with app.app_context():
        database = get_db()
        rows = database.execute(
            "SELECT id, name, image_url FROM attractions "
            "WHERE image_url LIKE 'http%' OR image_url LIKE '/api/attraction-image%'"
        ).fetchall()

        fixed = 0
        for row in rows:
            raw_url = row["image_url"]
            if raw_url.startswith("/api/attraction-image"):
                src = urllib.parse.unquote(
                    urlparse(raw_url).query.split("src=", 1)[-1]
                )
            else:
                src = raw_url
            path = _cache_path(src)
            if path.is_file() and path.stat().st_size > 0:
                continue  # 这张图能正常抓到，保持不动
            pick = names[row["id"] % pool]
            with db_transaction():
                database.execute(
                    "UPDATE attractions SET image_url = ? WHERE id = ?",
                    (pick, row["id"]),
                )
            fixed += 1

    print("为", fixed, "个缺图景点补上了风景照")


if __name__ == "__main__":
    main()
