"""
Platform Planner Daily Brief — v4 Final
기사 내용: Gemini 생성 / URL: 매체별 검색 URL 자동 생성 (깨짐 없음)
"""
import os, re, smtplib, sys, json
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib.request, urllib.parse

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
SMTP_EMAIL     = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD  = os.environ.get("SMTP_PASSWORD", "")
TARGET_EMAIL   = os.environ.get("TARGET_EMAIL", "seonyoung@ncsoft.com")
KST            = timezone(timedelta(hours=9))
MODEL          = "gemini-2.5-flash"

SYSTEM_PROMPT = """당신은 IT 업계 10년 차 플랫폼 기획 전문가입니다.
반드시 실제 존재하는 신뢰할 수 있는 매체의 기사만 사용하십시오.
(게임메카, 인벤, 루리웹, 이코리아, 전자신문, ZDNet, TechCrunch, Wired 등)
URL은 절대 포함하지 마십시오. 출처 매체명만 표기하십시오.
반드시 <html>로 시작해 </html>로 끝나는 순수 HTML만 출력."""


def build_prompt(today: str, yesterday: str) -> str:
    return f"""오늘: {today} (KST) / 기사 범위: {yesterday} 00:00 ~ {today} 09:00

[출력 조건 — 절대 준수]
  [카테고리 1] 🎮 국내 게임 시장  → 반드시 5개
  [카테고리 2] 🌐 글로벌 게임 시장 → 반드시 5개
  [카테고리 3] 💻 IT 업계          → 반드시 5개
  [카테고리 4] 🤖 AI               → 반드시 5개
  총합 = 정확히 20개.

각 기사마다:
  제목 / 키워드태그 3개 / 내용(2-3문장) / 요약(1줄) / 주목사유(2-3문장)
  출처: 매체명만 (예: 게임메카, 인벤, TechCrunch)
  URL은 절대 포함하지 말 것 — 코드에서 자동 생성함

[HTML 디자인 스펙]
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
전체 wrapper: max-width:680px; margin:0 auto; padding:20px; background:#fafaf8; font-family:'Noto Sans KR',sans-serif;
h1: font-size:18px; font-weight:700; color:#1a1a18; margin-bottom:4px;
날짜 부제: font-size:11px; color:#a0a095; font-family:monospace;

카테고리 헤더 pill:
  display:inline-flex; align-items:center; gap:8px; padding:6px 14px; border-radius:20px; font-size:13px; font-weight:700;
  국내게임 → background:#fef2ee; color:#c84b31;
  글로벌게임 → background:#eff6ff; color:#2563b0;
  IT업계 → background:#f5f3ff; color:#7c3aed;
  AI → background:#ecfeff; color:#0891b2;
  섹션 구분선: border-bottom:2px solid (카테고리 컬러); margin-bottom:16px;

기사 카드: border:1px solid #e8e6e0; border-radius:10px; padding:16px 18px; margin-bottom:10px; background:#ffffff;
기사 제목: font-size:13px; font-weight:700; color:#1a1a18; margin-bottom:6px; line-height:1.4;

키워드 chip (제목 바로 아래 가로 나열):
  display:flex; flex-direction:row; flex-wrap:wrap; gap:4px; margin-bottom:10px;
  chip: font-size:10px; font-weight:600; padding:3px 8px; border-radius:20px;
  카테고리별 색상 적용

내용/요약/주목사유/출처 row:
  display:grid; grid-template-columns:52px 1fr; gap:6px; margin-bottom:8px; align-items:baseline;
  라벨: font-size:10px; font-weight:700; color:#3d3d3a; font-family:monospace; letter-spacing:0.06em; text-transform:uppercase;
  텍스트: font-size:12px; color:#6b6b62; line-height:1.65;
  출처 라벨 아래: <span class="source-name" data-title="기사제목">매체명</span>
  (링크는 코드에서 자동 삽입 — HTML에 href 포함 금지)

20개 기사 모두 포함. 완전한 HTML 문서로 출력."""


MEDIA_SEARCH = {
    "게임메카":   "https://www.gamemeca.com/search/?keyword=",
    "인벤":       "https://www.inven.co.kr/search/webzine/?iskin=inven&query=",
    "루리웹":     "https://bbs.ruliweb.com/search?q=",
    "이코리아":   "https://www.ekoreanews.co.kr/news/search?keyword=",
    "전자신문":   "https://www.etnews.com/search?kwd=",
    "zdnet":      "https://zdnet.co.kr/search/?kwd=",
    "techcrunch": "https://techcrunch.com/search/",
    "wired":      "https://www.wired.com/search/?q=",
    "theverge":   "https://www.theverge.com/search?q=",
    "polygon":    "https://www.polygon.com/search?q=",
}

def inject_links(html: str) -> str:
    """source-name span을 찾아서 매체 검색 URL 링크로 교체"""
    def replace_span(m):
        title  = urllib.parse.quote(m.group(1))
        source = m.group(2).strip().lower()
        url    = next(
            (base + title for key, base in MEDIA_SEARCH.items() if key in source),
            f"https://search.naver.com/search.naver?where=news&query={title}"
        )
        return (
            f'<a href="{url}" target="_blank" '
            f'style="font-size:12px;color:#2563b0;text-decoration:underline;'
            f'text-underline-offset:2px;font-weight:500;">{m.group(2)}</a>'
        )
    return re.sub(
        r'<span class="source-name" data-title="([^"]+)">([^<]+)</span>',
        replace_span, html
    )


def generate_brief(today: str, yesterday: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents":           [{"parts": [{"text": build_prompt(today, yesterday)}]}],
        "generationConfig":   {"maxOutputTokens": 16000, "temperature": 0.5}
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    print("📡 Gemini 호출 중...")
    with urllib.request.urlopen(req, timeout=180) as res:
        data = json.loads(res.read().decode("utf-8"))
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    print("✅ 생성 완료")
    return text


def extract_html(raw: str) -> str:
    raw = re.sub(r"```html\s*|```\s*", "", raw, flags=re.IGNORECASE)
    m   = re.search(r"(<html[\s\S]*?</html>)", raw, re.IGNORECASE)
    return m.group(1).strip() if m else (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='UTF-8'></head>"
        "<body style='background:#fafaf8;padding:20px;max-width:680px;"
        "margin:auto;font-family:Noto Sans KR,sans-serif'>"
        f"{raw}</body></html>"
    )


def send_email(html: str, subject: str):
    msg            = MIMEMultipart("alternative")
    msg["From"]    = SMTP_EMAIL
    msg["To"]      = TARGET_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText("HTML 지원 클라이언트에서 확인하세요.", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    print(f"📧 발송 → {TARGET_EMAIL}")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SMTP_EMAIL, SMTP_PASSWORD)
        s.sendmail(SMTP_EMAIL, TARGET_EMAIL, msg.as_string())
    print("✅ 발송 완료!")


def main():
    now   = datetime.now(KST)
    today = now.strftime("%Y년 %m월 %d일")
    yest  = (now - timedelta(days=1)).strftime("%Y년 %m월 %d일")
    code  = now.strftime("%m%d")
    print(f"\n🗓  {today} 데일리 브리프 시작\n{'─'*48}")
    for v, n in [(GEMINI_API_KEY, "GEMINI_API_KEY"),
                 (SMTP_EMAIL,     "SMTP_EMAIL"),
                 (SMTP_PASSWORD,  "SMTP_PASSWORD")]:
        if not v:
            print(f"❌ 미설정: {n}"); sys.exit(1)

    raw_html = generate_brief(today, yest)
    html     = inject_links(extract_html(raw_html))
    subject  = f"[{code}] 플랫폼 기획자 데일리 브리프 | {today}"
    send_email(html, subject)
    print(f"\n🎉 완료: {subject}\n")


if __name__ == "__main__":
    main()
