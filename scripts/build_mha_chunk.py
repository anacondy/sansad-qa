import io
import json
import re
import urllib.request
import concurrent.futures
from datetime import datetime

from pypdf import PdfReader

INDEX_PAGES = [
    "https://www.mha.gov.in/MHA1/Par2017/ParBud2025.html",
    "https://www.mha.gov.in/MHA1/Par2017/ParWinter2025.html",
    "https://www.mha.gov.in/MHA1/Par2017/ParMonsoon2025.html",
]

TARGET_TOTAL = 279


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read()


def session_from_date(dt: datetime):
    if dt.month in (1, 2, 3, 4):
        return "Budget Session 2025", "Budget"
    if dt.month in (7, 8):
        return "Monsoon Session 2025", "Monsoon"
    if dt.month in (11, 12):
        return "Winter Session 2025", "Winter"
    return "Session 2025", "Session"


def extract_page_links(index_html: str):
    return sorted(
        set(
            re.findall(
                r"https://(?:www\.)?mha\.gov\.in/MHA1/Par2017/(?:LS|RS)\d{8}\.html",
                index_html,
                flags=re.I,
            )
        )
    )


def extract_pdf_links(page_html: str):
    links = sorted(
        set(
            re.findall(
                r"https://(?:www\.)?mha\.gov\.in/MHA1/Par2017/pdfs/par2025-pdfs/(?:LS|RS)\d{8}/\d+\.pdf",
                page_html,
                flags=re.I,
            )
        )
    )
    return links


def parse_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts = []
    for p in reader.pages:
        txt = p.extract_text() or ""
        if txt.strip():
            parts.append(txt.strip())
    return "\n".join(parts)


def split_question_answer(text: str):
    one = re.sub(r"\s+", " ", text).strip()
    q = one[:280]
    a = one[:260] + ("..." if len(one) > 260 else "")
    full = one[:5000]
    m = re.search(r"(?:QUESTION|Q\.?NO\.?|Unstarred|Starred)\s*[:\-]?\s*(.+?)(?:ANSWER|ANS\.?)\s*[:\-]?\s*(.+)", one, flags=re.I)
    if m:
        q = m.group(1).strip()[:280]
        full = m.group(2).strip()[:5000]
        a = full[:260] + ("..." if len(full) > 260 else "")
    return q, a, full


def make_record(pdf_url: str, text: str):
    m = re.search(r"/(LS|RS)(\d{2})(\d{2})(\d{4})/(\d+)\.pdf$", pdf_url, flags=re.I)
    if not m:
        return None
    house_code, dd, mm, yyyy, qno = m.groups()
    dt = datetime(int(yyyy), int(mm), int(dd))
    session_name, session_type = session_from_date(dt)
    house = "Lok Sabha" if house_code.upper() == "LS" else "Rajya Sabha"
    q, a, full = split_question_answer(text)
    if len(full) < 120:
        return None
    num_fmt = f"{house_code.upper()} Q{qno}"
    return {
        "id": int(f"25{dd}{mm}{qno}") if qno.isdigit() else abs(hash(pdf_url)) % 10_000_000,
        "question": q,
        "answer": a,
        "answerFull": full,
        "askedBy": "As per official PDF",
        "constituency": "As per official PDF",
        "party": "As per official PDF",
        "house": house,
        "session": session_name,
        "sessionType": session_type,
        "date": dt.strftime("%Y-%m-%d"),
        "questionType": "Unstarred",
        "questionNumber": num_fmt,
        "ministry": "Ministry of Home Affairs",
        "answeredBy": "As per official PDF",
        "answeredByRole": "As per official PDF",
        "tags": ["home affairs", "parliament", "official"],
        "source": pdf_url.replace("https://", "").replace("http://", ""),
    }


def main():
    page_links = []
    for idx in INDEX_PAGES:
        try:
            html = fetch(idx)
        except Exception:
            continue
        page_links.extend(extract_page_links(html))

    page_links = sorted(set(page_links))
    pdf_links = []
    for p in page_links:
        try:
            html = fetch(p)
        except Exception:
            continue
        pdf_links.extend(extract_pdf_links(html))

    pdf_links = sorted(set(pdf_links))
    records = []
    seen_ids = set()

    def process_pdf(pdf_url: str):
        try:
            pdf_bytes = fetch_bytes(pdf_url)
            text = parse_pdf_text(pdf_bytes)
            return make_record(pdf_url, text)
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        futures = {ex.submit(process_pdf, u): u for u in pdf_links}
        scanned = 0
        for fut in concurrent.futures.as_completed(futures):
            scanned += 1
            rec = fut.result()
            if not rec:
                continue
            if rec["id"] in seen_ids:
                rec["id"] = abs(hash(futures[fut])) % 100_000_000
            seen_ids.add(rec["id"])
            records.append(rec)
            if len(records) % 25 == 0:
                print(f"parsed={len(records)} / scanned={scanned}")
            if len(records) >= TARGET_TOTAL:
                for pending in futures:
                    if not pending.done():
                        pending.cancel()
                break

    with open("data/questions-chunk-004.json", "w", encoding="utf-8") as f:
        json.dump({"questions": records}, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(records)} records")


if __name__ == "__main__":
    main()
