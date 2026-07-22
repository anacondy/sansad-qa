import concurrent.futures
import json
import re
import urllib.request

TARGET_NEW_RECORDS = 279
START_PRID = 2109000
END_PRID = 2119999
TIMEOUT = 2.5
MAX_WORKERS = 80


def month_to_session(month: int):
    if month in (1, 2, 3, 4):
        return "Budget Session 2025", "Budget"
    if month in (7, 8):
        return "Monsoon Session 2025", "Monsoon"
    if month in (11, 12):
        return "Winter Session 2025", "Winter"
    return "Session 2025", "Session"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def extract_between(text: str, start: str, end: str) -> str:
    i = text.find(start)
    if i == -1:
        return ""
    i += len(start)
    j = text.find(end, i)
    if j == -1:
        return text[i:]
    return text[i:j]


def fetch_prid(prid: int):
    url = f"https://www.pib.gov.in/PressReleasePage.aspx?PRID={prid}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    if "PARLIAMENT QUESTION:" not in html:
        return None
    if "written reply" not in html.lower():
        return None

    title_match = re.search(r"<h2[^>]*>\s*(.*?)\s*</h2>", html, re.S | re.I)
    title = clean_text(re.sub(r"<[^>]+>", " ", title_match.group(1))) if title_match else "PARLIAMENT QUESTION"

    ministry = "Ministry of India"
    m = re.search(r"Ministry of\s+([^<\n]+)", html, re.I)
    if m:
        ministry = clean_text("Ministry of " + m.group(1))

    date_match = re.search(r"Posted On:\s*(\d{2})\s*([A-Z]{3})\s*(\d{4})", html)
    month_map = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
    }
    if date_match:
        day = int(date_match.group(1))
        month = month_map[date_match.group(2).upper()]
        year = int(date_match.group(3))
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
    else:
        date_str = "2025-01-01"
        month = 1

    session_name, session_type = month_to_session(month)

    house = "Lok Sabha"
    if re.search(r"Rajya Sabha", html, re.I):
        house = "Rajya Sabha"
    if re.search(r"in a written reply in the Lok Sabha today", html, re.I):
        house = "Lok Sabha"
    if re.search(r"in a written reply to a question in Rajya Sabha today", html, re.I):
        house = "Rajya Sabha"

    q_num = "Written Reply"
    q_match = re.search(r"\((Lok Sabha|Rajya Sabha)\s+US\s+Q(\d+)\)", html, re.I)
    if q_match:
        q_num = f"{q_match.group(1)} US Q{q_match.group(2)}"

    by_match = re.search(r"provided by\s+THE\s+(.+?)\s+in a written reply", html, re.I | re.S)
    answered_by = "Not specified"
    answered_by_role = "Minister"
    if by_match:
        by_text = clean_text(by_match.group(1))
        answered_by_role = by_text
        name_match = re.search(r"(SHRI|SMT\.?|DR\.)\s+([A-Z\.\s]+)$", by_text, re.I)
        if name_match:
            answered_by = clean_text(name_match.group(0).title())
        else:
            answered_by = by_text[-64:]

    plain = re.sub(r"<[^>]+>", " ", html)
    plain = clean_text(plain)
    body = extract_between(plain, title, "(Release ID:")
    if not body:
        body = extract_between(plain, "Posted On:", "(Release ID:")
    answer_full = clean_text(body)[:3000]
    answer = answer_full[:260] + ("..." if len(answer_full) > 260 else "")

    tag_tokens = set()
    for token in re.findall(r"[A-Za-z]{4,}", (title + " " + ministry).lower()):
        if token not in {"parliament", "question", "ministry", "india", "government", "written", "reply"}:
            tag_tokens.add(token)
    tags = sorted(list(tag_tokens))[:4] or ["governance"]

    return {
        "id": prid,
        "question": title,
        "answer": answer,
        "answerFull": answer_full,
        "askedBy": "Not specified in PIB release",
        "constituency": "N/A",
        "party": "N/A",
        "house": house,
        "session": session_name,
        "sessionType": session_type,
        "date": date_str,
        "questionType": "Unstarred",
        "questionNumber": q_num,
        "ministry": ministry,
        "answeredBy": answered_by,
        "answeredByRole": answered_by_role,
        "tags": tags,
        "source": f"pib.gov.in/PressReleasePage.aspx?PRID={prid}"
    }


def main():
    results = []
    seen_ids = set()
    prids = list(range(START_PRID, END_PRID + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_prid, prid): prid for prid in prids}
        scanned = 0
        for fut in concurrent.futures.as_completed(futures):
            scanned += 1
            try:
                row = fut.result()
            except Exception:
                row = None
            if row and row["id"] not in seen_ids:
                seen_ids.add(row["id"])
                results.append(row)
                if len(results) % 25 == 0:
                    print(f"collected={len(results)} scanned={scanned}")
            if len(results) >= TARGET_NEW_RECORDS:
                for pending in futures:
                    if not pending.done():
                        pending.cancel()
                break

    results = sorted(results, key=lambda x: x["date"])
    payload = {"questions": results[:TARGET_NEW_RECORDS]}
    with open("data/questions-chunk-004.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(payload['questions'])} records")


if __name__ == "__main__":
    main()
