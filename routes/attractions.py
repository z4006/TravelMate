"""景点查询 API。"""

import hashlib
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from flask import Blueprint, redirect, request, send_file

from database.attractions import (
    get_attraction_by_id,
    list_attractions,
    list_categories,
)
from database.connection import get_db
from utils.responses import api_response


attractions_bp = Blueprint("attractions", __name__)

# 图片本地缓存：直连图源会限流或防盗链，逐张缓存到本地后由本站提供
IMAGE_HOSTS = {
    "upload.wikimedia.org",
    "img0.baidu.com",
    "img1.baidu.com",
    "img2.baidu.com",
    "img3.baidu.com",
    "img4.baidu.com",
    "img5.baidu.com",
}
WIKIMEDIA_HOST = "upload.wikimedia.org"
IMAGE_CACHE = Path(__file__).resolve().parents[1] / "data" / "image-cache"
# Wikimedia 只允许预设缩略图宽度，实测 500 与 1280 可用
THUMB_WIDTHS = (500, 1280)
FETCH_TIMEOUT = 20


def _proxied_image(url: str) -> str:
    """把外部图片地址改成本站缓存入口；本地资源原样返回。"""

    if not url or not url.startswith(("http://", "https://")):
        return url
    if urllib.parse.urlparse(url).netloc not in IMAGE_HOSTS:
        return url
    return "/api/attraction-image?src=" + urllib.parse.quote(url, safe="")


def _thumb_urls(url: str) -> list[str]:
    """生成允许宽度内的缩略图地址，原图作为最后兜底。"""

    marker = "/commons/"
    if urllib.parse.urlparse(url).netloc != WIKIMEDIA_HOST or marker not in url:
        return [url]
    head, tail = url.split(marker, 1)
    filename = tail.rsplit("/", 1)[-1]
    thumbs = [
        f"{head}{marker}thumb/{tail}/{width}px-{filename}"
        for width in THUMB_WIDTHS
    ]
    return thumbs + [url]


@attractions_bp.get("/api/attraction-image")
def attraction_image():
    """按需抓取并缓存景点图片，抓取失败时回退到原始地址。"""

    src = (request.args.get("src") or "").strip()
    parsed = urllib.parse.urlparse(src)
    if parsed.scheme != "https" or parsed.netloc not in IMAGE_HOSTS:
        return redirect("/static/images/placeholder-attraction.svg")

    suffix = Path(parsed.path).suffix.lower() or ".jpg"
    cache_path = IMAGE_CACHE / (hashlib.sha256(src.encode()).hexdigest() + suffix)
    if not cache_path.is_file():
        if not _download_image(src, cache_path):
            return redirect(src)
    response = send_file(cache_path, conditional=True, max_age=604800)
    response.headers["Cache-Control"] = "public, max-age=604800"
    return response


def _download_image(src: str, target: Path) -> bool:
    """下载并落盘；遇到 429 时短暂退避重试。"""

    target.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
        "Referer": "https://image.baidu.com/",
    }
    for url in _thumb_urls(src):
        for attempt in range(2):
            try:
                request_ = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request_, timeout=FETCH_TIMEOUT) as resp:
                    payload = resp.read()
                if payload:
                    tmp = target.with_suffix(target.suffix + ".part")
                    tmp.write_bytes(payload)
                    tmp.replace(target)
                    return True
            except urllib.error.HTTPError as error:
                if error.code == 429:
                    time.sleep(2 * (attempt + 1))
                    continue
                break
            except Exception:  # noqa: BLE001 - 抓取失败统一回退
                break
    return False


def _public_attraction(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "category": {
            "id": row["category_id"],
            "name": row["category_name"],
            "slug": row["category_slug"],
        },
        "city": row["city"],
        "address": row["address"],
        "phone": row["phone"],
        "description": row["description"],
        "ticket_price_cents": row["ticket_price_cents"],
        "opening_hours": row["opening_hours"],
        "image_url": _proxied_image(row["image_url"]),
        "source": row["source"],
        "source_id": row["source_id"],
        "source_url": row["source_url"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@attractions_bp.get("/api/attractions")
def attractions():
    """分页查询公开景点，可按分类、城市和关键词筛选。"""

    try:
        page = int(request.args.get("page", "1"))
        page_size = int(request.args.get("page_size", "20"))
    except ValueError:
        return api_response(False, "分页参数必须是整数", None, 400)
    if page < 1 or not 1 <= page_size <= 1000:
        return api_response(False, "分页参数不合法", None, 400)

    category = request.args.get("category", "").strip()
    city = request.args.get("city", "").strip()
    keyword = (request.args.get("q") or request.args.get("keyword") or "").strip()
    if any(len(value) > 100 for value in (category, city, keyword)):
        return api_response(False, "筛选参数不能超过 100 个字符", None, 400)

    rows, total = list_attractions(
        get_db(),
        category or None,
        city or None,
        keyword or None,
        page_size,
        (page - 1) * page_size,
    )
    return api_response(
        True,
        "操作成功",
        {
            "items": [_public_attraction(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@attractions_bp.get("/api/attractions/categories")
def attraction_categories():
    """查询景点分类。"""

    categories = [
        {"id": row["id"], "name": row["name"], "slug": row["slug"]}
        for row in list_categories(get_db())
    ]
    return api_response(True, "操作成功", {"items": categories})


@attractions_bp.get("/api/attractions/<attraction_id>")
def attraction_detail(attraction_id: str):
    """查询单个公开景点。"""

    try:
        parsed_id = int(attraction_id)
    except ValueError:
        return api_response(False, "景点 ID 不合法", None, 400)
    if parsed_id < 1:
        return api_response(False, "景点 ID 不合法", None, 400)

    row = get_attraction_by_id(get_db(), parsed_id)
    if row is None:
        return api_response(False, "景点不存在", None, 404)
    return api_response(True, "操作成功", _public_attraction(row))
