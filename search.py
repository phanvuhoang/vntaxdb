import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

openai_client = None


def get_openai_client():
    global openai_client
    if openai_client is None and OPENAI_API_KEY:
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return openai_client


async def get_embedding(text_input: str) -> list[float] | None:
    """Get embedding from OpenAI text-embedding-3-small."""
    client = get_openai_client()
    if not client:
        return None
    try:
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text_input
        )
        return response.data[0].embedding
    except Exception:
        return None


async def fulltext_search_documents(db: AsyncSession, query: str, filters: dict, limit: int = 50, offset: int = 0):
    """Full-text search on documents table."""
    conditions = []
    params = {"limit": limit, "offset": offset}

    if query:
        conditions.append(
            "to_tsvector('simple', so_hieu || ' ' || ten || ' ' || COALESCE(tom_tat,'') || ' ' || COALESCE(noi_dung,'')) "
            "@@ plainto_tsquery('simple', :query)"
        )
        params["query"] = query

    if filters.get("loai"):
        conditions.append("loai = :loai")
        params["loai"] = filters["loai"]

    if filters.get("sac_thue"):
        conditions.append(":sac_thue = ANY(sac_thue)")
        params["sac_thue"] = filters["sac_thue"]

    if filters.get("tinh_trang"):
        if filters["tinh_trang"] == "con_hieu_luc":
            conditions.append("tinh_trang ILIKE '%còn hiệu lực%'")
        elif filters["tinh_trang"] == "het_hieu_luc":
            conditions.append("tinh_trang ILIKE '%hết hiệu lực%'")

    if filters.get("year"):
        conditions.append("EXTRACT(YEAR FROM ngay_ban_hanh) = :year")
        params["year"] = int(filters["year"])

    where = " AND ".join(conditions) if conditions else "1=1"

    count_sql = f"SELECT COUNT(*) FROM documents WHERE {where}"
    count_result = await db.execute(text(count_sql), params)
    total = count_result.scalar()

    sql = f"""
        SELECT id, so_hieu, ten, loai, co_quan, ngay_ban_hanh, hieu_luc_tu,
               tinh_trang, sac_thue, tu_khoa, tom_tat, link_tvpl, link_vbpl, luu_y,
               category
        FROM documents
        WHERE {where}
        ORDER BY ngay_ban_hanh DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return {"total": total, "items": [dict(r) for r in rows]}


async def fulltext_search_cong_van(db: AsyncSession, query: str, filters: dict, limit: int = 50, offset: int = 0):
    """Full-text search on cong_van table."""
    conditions = []
    params = {"limit": limit, "offset": offset}

    if query:
        conditions.append(
            "to_tsvector('simple', so_hieu || ' ' || COALESCE(ten,'') || ' ' || COALESCE(ket_luan,'')) "
            "@@ plainto_tsquery('simple', :query)"
        )
        params["query"] = query

    if filters.get("co_quan"):
        conditions.append("co_quan ILIKE :co_quan")
        params["co_quan"] = f"%{filters['co_quan']}%"

    if filters.get("sac_thue"):
        conditions.append(":sac_thue = ANY(sac_thue)")
        params["sac_thue"] = filters["sac_thue"]

    if filters.get("year"):
        conditions.append("EXTRACT(YEAR FROM ngay_ban_hanh) = :year")
        params["year"] = int(filters["year"])

    where = " AND ".join(conditions) if conditions else "1=1"

    count_sql = f"SELECT COUNT(*) FROM cong_van WHERE {where}"
    count_result = await db.execute(text(count_sql), params)
    total = count_result.scalar()

    sql = f"""
        SELECT id, so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, ket_luan,
               tags, link_tvpl
        FROM cong_van
        WHERE {where}
        ORDER BY ngay_ban_hanh DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return {"total": total, "items": [dict(r) for r in rows]}


async def semantic_search(db: AsyncSession, query: str, table: str = "documents", limit: int = 5):
    """Semantic search using pgvector cosine distance."""
    embedding = await get_embedding(query)
    if not embedding:
        return []

    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    if table == "documents":
        sql = text(f"""
            SELECT id, so_hieu, ten, loai, co_quan, ngay_ban_hanh, tinh_trang,
                   tom_tat, noi_dung, luu_y,
                   1 - (embedding <=> :embedding::vector) as similarity
            FROM documents
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """)
    else:
        sql = text(f"""
            SELECT id, so_hieu, ten, co_quan, ngay_ban_hanh, ket_luan,
                   noi_dung_day_du,
                   1 - (embedding <=> :embedding::vector) as similarity
            FROM cong_van
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """)

    result = await db.execute(sql, {"embedding": embedding_str, "limit": limit})
    rows = result.mappings().all()
    return [dict(r) for r in rows]


async def combined_search(db: AsyncSession, query: str, search_type: str = "all",
                          filters: dict = None, limit: int = 50, offset: int = 0):
    """Combined search across documents and cong_van."""
    filters = filters or {}
    results = {}

    if search_type in ("all", "document"):
        results["documents"] = await fulltext_search_documents(db, query, filters, limit, offset)

    if search_type in ("all", "cong_van"):
        results["cong_van"] = await fulltext_search_cong_van(db, query, filters, limit, offset)

    return results
