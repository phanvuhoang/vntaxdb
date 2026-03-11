import os
import anthropic

CLAUDIBLE_API_KEY = os.getenv("CLAUDIBLE_API_KEY", "")
CLAUDIBLE_BASE_URL = os.getenv("CLAUDIBLE_BASE_URL", "https://claudible.io/v1")
CLAUDIBLE_MODEL = os.getenv("CLAUDIBLE_MODEL", "claude-sonnet-4-6")


def get_claude_client():
    if not CLAUDIBLE_API_KEY:
        return None
    return anthropic.Anthropic(
        api_key=CLAUDIBLE_API_KEY,
        base_url=CLAUDIBLE_BASE_URL
    )


def extract_cong_van_fields(raw_text: str) -> dict:
    """Use Claude to extract structured fields from a công văn."""
    client = get_claude_client()
    if not client:
        return {}

    response = client.messages.create(
        model=CLAUDIBLE_MODEL,
        max_tokens=2000,
        system="Bạn là chuyên gia phân tích văn bản pháp luật thuế Việt Nam. Trích xuất thông tin từ công văn.",
        messages=[{
            "role": "user",
            "content": f"""Phân tích công văn sau và trả về JSON với các trường:
- ket_luan: Kết luận chính của công văn (1-2 câu)
- van_ban_trich_dan: Array các văn bản được trích dẫn, mỗi item có {{so_hieu, dieu, khoan, muc}}
- tags: Array tags mô tả nội dung (vd: ["CIT", "chi phí được trừ", "khấu hao"])
- sac_thue: Array sắc thuế liên quan ["CIT", "VAT", "PIT", "FCT", "SCT", "XNK"]

Chỉ trả về JSON, không giải thích.

Công văn:
{raw_text[:8000]}"""
        }]
    )

    import json
    try:
        content = response.content[0].text
        # Try to extract JSON from the response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return json.loads(content.strip())
    except (json.JSONDecodeError, IndexError):
        return {}


def stream_chat_response(system_prompt: str, context: str, question: str):
    """Stream Claude response for chatbox."""
    client = get_claude_client()
    if not client:
        yield "Lỗi: Chưa cấu hình API key cho AI chatbox."
        return

    messages = [{
        "role": "user",
        "content": f"""Context từ database pháp luật thuế:
---
{context}
---

Câu hỏi: {question}"""
    }]

    with client.messages.stream(
        model=CLAUDIBLE_MODEL,
        max_tokens=4000,
        system=system_prompt,
        messages=messages,
    ) as stream:
        for text_chunk in stream.text_stream:
            yield text_chunk
