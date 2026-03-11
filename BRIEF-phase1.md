# BRIEF: VietTax Legal DB — Phase 1 MVP

## Overview
Web app tra cứu văn bản pháp luật thuế Việt Nam với AI chatbox.
Tương tự taxsector về stack nhưng có PostgreSQL + pgvector + multi-user.

## Tech Stack
- **Backend:** FastAPI (Python 3.11)
- **Database:** PostgreSQL 16 + pgvector extension
- **Frontend:** Single HTML file, Tailwind CSS CDN, vanilla JS
- **Auth:** JWT (python-jose), bcrypt
- **AI:** Claudible API (claude-sonnet-4.6) cho chatbox + extract
- **Embeddings:** OpenAI text-embedding-3-small (cho semantic search)
- **Deploy:** Docker + Coolify, domain legaldb.gpt4vn.com
- **Primary color:** #028a39

## File Structure
```
viet-tax-legaldb/
├── main.py              # FastAPI app — tất cả routes
├── models.py            # SQLAlchemy models
├── database.py          # DB connection, init
├── crawler.py           # TVPL + vbpl.vn crawler
├── ai_extract.py        # Claude extract CV fields
├── search.py            # Full-text + semantic search
├── requirements.txt
├── Dockerfile
├── .env.example
└── data/
    └── seed_legal_db.json   # Import từ all_merged.json hiện có
```

## Database Schema (PostgreSQL)

```sql
-- Users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role VARCHAR(20) DEFAULT 'user',  -- 'admin' | 'user'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Văn bản pháp luật (Luật, NĐ, TT)
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    so_hieu VARCHAR(100) UNIQUE NOT NULL,
    ten TEXT NOT NULL,
    loai VARCHAR(20) NOT NULL,       -- Luat | ND | TT | QD | NQ
    co_quan VARCHAR(200),
    ngay_ban_hanh DATE,
    hieu_luc_tu DATE,
    het_hieu_luc_tu DATE,
    tinh_trang VARCHAR(30),          -- con_hieu_luc | het_hieu_luc | chua_hieu_luc
    thay_the_boi VARCHAR(100),       -- so_hieu của VB thay thế
    sua_doi_boi TEXT,                -- JSON array các so_hieu sửa đổi
    sac_thue VARCHAR(20)[],          -- {CIT, VAT, PIT, FCT, SCT, XNK}
    category TEXT[],                 -- {chuyen_gia, hoa_don, khan_tru...}
    tom_tat TEXT,
    noi_dung TEXT,                   -- full text nếu crawl được
    link_tvpl TEXT,
    link_vbpl TEXT,
    tu_khoa TEXT[],
    embedding vector(1536),          -- pgvector, OpenAI text-embedding-3-small
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Công văn
CREATE TABLE cong_van (
    id SERIAL PRIMARY KEY,
    so_hieu VARCHAR(100) UNIQUE NOT NULL,
    ten TEXT,
    co_quan VARCHAR(200),            -- TCT | BTC | Cuc Thue HN...
    nguoi_nhan TEXT,
    ngay_ban_hanh DATE,
    sac_thue VARCHAR(20)[],
    van_ban_trich_dan JSONB,         -- [{so_hieu, dieu, khoan, muc}]
    ket_luan TEXT,                   -- AI-extracted kết luận chính
    noi_dung_day_du TEXT,
    tags TEXT[],                     -- AI-generated tags
    link_tvpl TEXT,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Legal Issues Index (AI-generated)
CREATE TABLE legal_issues (
    id SERIAL PRIMARY KEY,
    title VARCHAR(300) NOT NULL,     -- "Chi phí thuê nhà TNDN"
    description TEXT,
    sac_thue VARCHAR(20)[],
    tags TEXT[],
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Many-to-many: issue <-> document/cong_van
CREATE TABLE issue_refs (
    id SERIAL PRIMARY KEY,
    issue_id INTEGER REFERENCES legal_issues(id),
    ref_type VARCHAR(20),            -- 'document' | 'cong_van'
    ref_id INTEGER,
    relevance_score FLOAT,
    note TEXT                        -- ghi chú tại sao liên quan
);

-- Full-text search index
CREATE INDEX idx_documents_fts ON documents 
    USING GIN(to_tsvector('simple', so_hieu || ' ' || ten || ' ' || COALESCE(noi_dung,'')));
CREATE INDEX idx_cong_van_fts ON cong_van 
    USING GIN(to_tsvector('simple', so_hieu || ' ' || COALESCE(ten,'') || ' ' || COALESCE(ket_luan,'')));
```

## API Endpoints

### Auth
```
POST /auth/login          → {access_token}
POST /auth/register       → admin only
GET  /auth/me             → current user info
```

### Documents (Luật/NĐ/TT)
```
GET  /api/documents                → list, filter: sac_thue, loai, tinh_trang, year, q
GET  /api/documents/{so_hieu}      → detail + related CVs
GET  /api/documents/{so_hieu}/relations → VB thay thế/sửa đổi
```

### Công văn
```
GET  /api/cong-van                 → list, filter: co_quan, sac_thue, year, q
GET  /api/cong-van/{so_hieu}       → detail
```

### Search
```
GET  /api/search?q=...&type=all|document|cong_van&sac_thue=CIT
     → full-text search across both tables
```

### AI Chatbox
```
POST /api/chat
     body: {question: "Chi phí thuê nhà 2026 được khấu trừ không?"}
     → stream response với format:
        1. Quy định áp dụng (trích dẫn cụ thể)
        2. Công văn hướng dẫn liên quan
        3. Rủi ro + lưu ý
        4. Đề xuất hướng khắc phục
```

### Export
```
POST /api/export/word
     body: {type: 'search_results'|'document'|'chat_answer', data: {...}}
     → .docx file download
```

### Admin
```
GET  /api/admin/stats              → tổng số VB, CV, users
POST /api/admin/crawl              → trigger manual crawl
GET  /api/admin/users              → list users
POST /api/admin/users              → create user
```

## Frontend (single HTML)

### Layout
```
Header: Logo "VietTax Legal DB" | Nav: Tra cứu / Chatbox / Admin | User menu
─────────────────────────────────────────────────────────────────
Sidebar (left 280px):
  Filters:
    - Loại: [Luật][NĐ][TT][Công văn]
    - Sắc thuế: [CIT][VAT][PIT][FCT][SCT][XNK]
    - Hiệu lực: [Còn][Hết][Tất cả]
    - Năm: dropdown
    
Main (center):
  Search bar (lớn, prominent)
  Results list:
    - Card: số hiệu | tên | loại badge | sắc thuế tags | hiệu lực badge | ngày
    - Click → modal detail
  
  Detail modal:
    - Header: số hiệu, tên, badges
    - Tabs: [Thông tin] [Nội dung] [Văn bản liên quan] [Công văn hướng dẫn]
    - Nút: [📋 Copy link] [🔗 TVPL] [📄 Xuất Word]

Chatbox tab:
  - Chat interface (messages bubble)
  - Input: "Đặt câu hỏi về thuế..." + [Gửi]
  - Mỗi answer có nút [📄 Xuất Word]
  - Streaming response
```

### UI Notes
- Responsive (mobile-friendly)
- Dark/light mode (optional, có thể bỏ)
- Loading states cho crawl + AI
- Toast notifications

## AI Chatbox Logic (main.py)

```python
@app.post("/api/chat")
async def chat(request: ChatRequest, user = Depends(get_current_user)):
    question = request.question
    
    # 1. Semantic search trong DB
    relevant_docs = await semantic_search(question, limit=5)
    relevant_cvs = await semantic_search_cv(question, limit=5)
    
    # 2. Build context
    context = build_legal_context(relevant_docs, relevant_cvs)
    
    # 3. Stream Claude response
    system_prompt = """Bạn là chuyên gia tư vấn thuế Việt Nam.
    Dựa trên các văn bản pháp luật và công văn được cung cấp, hãy trả lời câu hỏi.
    
    Format trả lời BẮT BUỘC:
    ## 1. Quy định áp dụng
    [Trích dẫn cụ thể: điều/khoản/mục của Luật/NĐ/TT, ghi rõ còn hiệu lực hay không]
    
    ## 2. Công văn hướng dẫn liên quan
    [Số CV, cơ quan ban hành, ngày, kết luận chính]
    
    ## 3. Rủi ro & lưu ý
    [Các trường hợp không được áp dụng, điều kiện cần đáp ứng]
    
    ## 4. Đề xuất
    [Hướng xử lý thực tế]
    
    QUAN TRỌNG: Chỉ trích dẫn văn bản có trong context. Ghi rõ nếu không tìm thấy quy định cụ thể."""
    
    yield from stream_claude(system_prompt, context, question)
```

## Crawler (crawler.py)

### Phase 1: vbpl.vn (không cần login)
```python
# Base URL: https://vbpl.vn/TW/Pages/vbpq-van-ban-phap-luat.aspx
# Filter: loaiVanBan=1 (Luật), 2 (NĐ), 3 (TT)
# co_quan: BTC, TCT
# Full text: https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID={id}
```

### Phase 2: TVPL với Playwright (cho Công văn)
```python
# Login → search công văn TCT/BTC → extract 4 fields
# Rate limit: 1 request/2s, max 100 CV/run
```

## Environment Variables
```env
DATABASE_URL=postgresql://user:pass@host:5432/legaldb
JWT_SECRET=random_secret_key
JWT_EXPIRE_HOURS=24
CLAUDIBLE_API_KEY=...
CLAUDIBLE_BASE_URL=https://claudible.io/v1
CLAUDIBLE_MODEL=claude-sonnet-4.6
OPENAI_API_KEY=...   # cho embeddings (text-embedding-3-small)
TVPL_USERNAME=pvhptm
TVPL_PASSWORD=368Charter
APP_VERSION=1.0.0
```

## Requirements.txt
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
asyncpg==0.29.0
alembic==1.13.0
pgvector==0.3.5
python-jose[cryptography]==3.3.0
bcrypt==4.1.3
httpx==0.27.0
beautifulsoup4==4.12.3
playwright==1.47.0
openai==1.51.0
anthropic==0.40.0
python-docx==1.1.2
python-multipart==0.0.12
pydantic==2.9.2
python-dotenv==1.0.1
```

## Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Seed Data
File `data/seed_legal_db.json` = copy của `all_merged.json` (367 VB đã có).
Khi app start lần đầu, tự động import nếu DB trống:
```python
@app.on_event("startup")
async def seed_db():
    if await db.count(Document) == 0:
        await import_from_json("data/seed_legal_db.json")
```

## Phase 1 Deliverables
- [ ] App chạy được trên port 8000
- [ ] Login/register (admin tạo user)
- [ ] Search full-text hoạt động
- [ ] Filter sidebar hoạt động
- [ ] Detail modal với 4 tabs
- [ ] AI Chatbox stream response
- [ ] Export Word (search results + chat answer)
- [ ] Import 367 VB từ seed file
- [ ] Crawler vbpl.vn metadata (manual trigger từ admin panel)

## Coolify Setup (anh cần làm)
1. Tạo PostgreSQL service trên Coolify (Coolify có sẵn template)
   - Database name: `legaldb`
   - User: `legaldb_user`
   - Password: tự đặt
2. Enable pgvector: vào PostgreSQL container, chạy:
   `CREATE EXTENSION IF NOT EXISTS vector;`
3. Thêm các env vars vào app (xem danh sách trên)
4. Add persistent volume: `legaldb-data` → `/app/data`

## Commit Message cho lần đầu
`feat: initial Phase 1 MVP — FastAPI + PostgreSQL + pgvector + AI chatbox`

## Sau khi xong
Xoá BRIEF-phase1.md, push lên main.
Nhắn Thanh để deploy lên Coolify.
