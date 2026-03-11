import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

VBPL_BASE = "https://vbpl.vn"
VBPL_LIST = f"{VBPL_BASE}/TW/Pages/vbpq-van-ban-phap-luat.aspx"
VBPL_DETAIL = f"{VBPL_BASE}/TW/Pages/vbpq-toanvan.aspx"

# Mapping loaiVanBan param
LOAI_VB_MAP = {
    "Luật": "1",
    "Nghị định": "2",
    "Thông tư": "3",
}


async def crawl_vbpl_list(loai: str = "Luật", co_quan: str = "BTC", page: int = 1) -> list[dict]:
    """Crawl document list from vbpl.vn."""
    results = []
    params = {
        "loaiVanBan": LOAI_VB_MAP.get(loai, "1"),
        "page": page
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(VBPL_LIST, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch vbpl list: {e}")
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("div.item, tr.item, .content-area li, .vbItem")

        for item in items:
            try:
                link_el = item.select_one("a[href]")
                if not link_el:
                    continue

                title = link_el.get_text(strip=True)
                href = link_el["href"]
                if not href.startswith("http"):
                    href = VBPL_BASE + href

                # Extract ItemID from URL
                item_id = None
                match = re.search(r"ItemID=(\d+)", href)
                if match:
                    item_id = match.group(1)

                # Try to extract so_hieu from title
                so_hieu_match = re.match(r"^([\d/\-]+[A-ZĐa-zđ\-/]+)", title)
                so_hieu = so_hieu_match.group(1) if so_hieu_match else title[:50]

                results.append({
                    "so_hieu": so_hieu,
                    "ten": title,
                    "loai": loai,
                    "link_vbpl": href,
                    "item_id": item_id,
                })
            except Exception as e:
                logger.warning(f"Error parsing item: {e}")
                continue

    return results


async def crawl_vbpl_detail(item_id: str) -> dict | None:
    """Crawl full text of a document from vbpl.vn."""
    url = f"{VBPL_DETAIL}?ItemID={item_id}"

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch detail {item_id}: {e}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract metadata
        metadata = {}

        # Full text content
        content_div = soup.select_one(".fulltext, .content, #toanvancontent, .box-ct")
        if content_div:
            metadata["noi_dung"] = content_div.get_text(separator="\n", strip=True)

        # Try to get co_quan, ngay_ban_hanh from metadata table
        info_table = soup.select("table.info tr, .att-item, .box-info tr")
        for row in info_table:
            label_el = row.select_one("td:first-child, .att-title, th")
            value_el = row.select_one("td:last-child, .att-content, td + td")
            if not label_el or not value_el:
                continue
            label = label_el.get_text(strip=True).lower()
            value = value_el.get_text(strip=True)

            if "cơ quan" in label or "ban hành" in label:
                metadata["co_quan"] = value
            elif "ngày" in label and "ban hành" in label:
                try:
                    metadata["ngay_ban_hanh"] = datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass
            elif "hiệu lực" in label:
                try:
                    metadata["hieu_luc_tu"] = datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass
            elif "tình trạng" in label:
                metadata["tinh_trang"] = value

        return metadata


async def run_crawl(loai: str = "Luật", max_pages: int = 3) -> list[dict]:
    """Run a full crawl session for a document type."""
    all_docs = []

    for page in range(1, max_pages + 1):
        docs = await crawl_vbpl_list(loai=loai, page=page)
        if not docs:
            break

        for doc in docs:
            if doc.get("item_id"):
                detail = await crawl_vbpl_detail(doc["item_id"])
                if detail:
                    doc.update(detail)
                await asyncio.sleep(1)  # Rate limiting

            all_docs.append(doc)

        logger.info(f"Crawled page {page}: {len(docs)} documents")
        await asyncio.sleep(2)

    return all_docs
