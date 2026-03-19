"""
Platform Planner Daily Brief — v6
1단계: Google Search 그라운딩으로 실제 기사 목록 수집 (텍스트)
2단계: 수집된 목록으로 HTML 뉴스레터 생성 (그라운딩 없이)
→ URL 깨짐 문제 + 빈 메일 문제 동시 해결
"""
import os, re, smtplib, sys, json
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib.request

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
SMTP_EMAIL     = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD  = os.environ.get("SMTP_PASSWORD", "")
TARGET_EMAIL   = os.environ.get("TARGET_EMAIL", "seonyoung@ncsoft.com")
KST            = timezone(timedelta(hours=9))
MODEL          = "gemini-2.5-flash"


# ─── 공통 API 호출 헬퍼 ────────────────────
def call_gemini(system: str, user: str, max_tokens: int, use_search: bool) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3},
    }
    if use_search:
        body["tools"] = [{"google_search": {}}]

    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=180) as res:
        data = json.loads(res.read().decode("utf-8"))

    # 모든 text 파트 합치기 (그라운딩 응답은 파트가 여럿일 수 있음)
    text = ""
    for part in data["candidates"][0]["content"]["parts"]:
        if "text" in part:
            text += part["text"]
    return text


# ─── 1단계: 실제 기사 목록 수집 (그라운딩 ON) ─
def fetch_articles(today: str, yesterday: str) -> str:
    system = """당신은 뉴스 리서처입니다.
Google 검색으로 실제 존재하는 기사만 수집하십시오.
URL은 반드시 검색으로 확인된 실제 링크만 사용하십시오.
출력 형식: 순수 텍스트 목록만. HTML 금지."""

    user = f"""아래 4개 카테고리에서 각 5개씩, 총 20개 기사를 검색하십시오.
기사 범위: {yesterday} 00:00 ~ {today} 09:00 (24시간 이내)

[카테고리 1] 국내 게임 시장 (게임메카, 인벤, 루리웹 등 국내 매체)
[카테고리 2] 글로벌 게임 시장 (IGN, TechCrunch, Polygon 등)
[카테고리 3] IT 업계 (전자신문, ZDNet, The Verge 등)
[카테고리 4] AI (VentureBeat, Wired, MIT Tech Review 등)

각 기사를 아래 형식으로 출력하십시오:
[카테고리명]
제목: (기사 제목)
URL: (실제 원문 URL)
요약: (핵심 내용 1-2줄)
---"""

    print("📡 1단계: Google Search로 기사 수집 중...")
    result = call_gemini(system, user, max_tokens=4000, use_search=True)
    print("✅ 1단계 완료 — 기사 목록 수집됨")
    return result


# ─── 2단계: HTML 뉴스레터 생성 (그라운딩 OFF) ─
def generate_html(today: str, articles: str) -> str:
    system = """당신은 IT 업계 10년 차 플랫폼 기획 전문가입니다.
주어진 기사 목록을 바탕으로 HTML 뉴스레터를 생성합니다.
URL은 반드시 제공된 목록의 URL 그대로 사용. 절대 변경 금지.
반드시 <html>로 시작해 </html>로 끝나는 순수 HTML만 출력."""

    user = f"""아래 기사 목록을 HTML 뉴스레터로 변환하십시오.
오늘 날짜: {today}

=== 수집된 기사 목록 ===
{articles}
========================

[HTML 디자인 스펙]
Google Fonts:
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">

전체 wrapper:
  max-width:680px; margin:0 auto; padding:20px;
  background:#fafaf8; font-family:'Noto Sans KR',sans-serif;

헤더:
  h1: font-size:18px; font-weight:700; color:#1a1a18; margin-bottom:4px;
  날짜 부제: font-size:11px; color:#a0a095; font-family:monospace;

카테고리 섹션 헤더 (pill 형태):
  display:inline-flex; align-items:center; gap:8px;
  padding:6px 14px; border-radius:20px; font-size:13px; font-weight:700;
  국내게임  → background:#fef2ee; color:#c84b31;
  글로벌게임 → background:#eff6ff; color:#2563b0;
  IT업계    → background:#f5f3ff; color:#7c3aed;
  AI        → background:#ecfeff; color:#0891b2;
  섹션 구분선: border-bottom:2px solid (카테고리 컬러); margin-bottom:16px;

기사 카드:
  border:1px solid #e8e6e0; border-radius:10px;
  padding:16px 18px; margin-bottom:10px; background:#ffffff;

기사 제목:
  font-size:13px; font-weight:700; color:#1a1a18;
  margin-bottom:6px; line-height:1.4;

키워드 chip (제목 바로 아래 한 줄, 가로 나열):
  display:flex; flex-direction:row; flex-wrap:wrap; gap:4px; margin-bottom:10px;
  각 chip → font-size:10px; font-weight:600; padding:3px 8px;
             border-radius:20px; white-space:nowrap;
  국내게임 chip  → background:#fef2ee; color:#c84b31;
  글로벌게임 chip → background:#eff6ff; color:#2563b0;
  IT chip        → background:#f5f3ff; color:#7c3aed;
  AI chip        → background:#ecfeff; color:#0891b2;

내용/요약/주목사유/링크 row:
  display:grid; grid-template-columns:52px 1fr; gap:6px;
  margin-bottom:8px; align-items:baseline;

  라벨(내용/요약/주목사유/링크):
    font-size:10px; font-weight:700; color:#3d3d3a;
    font-family:monospace; letter-spacing:0.06em;
    text-transform:uppercase; padding-top:2px;

  내용/요약/주목사유 텍스트: font-size:12px; color:#6b6b62; line-height:1.65;

  링크: <a href="수집된 목록의 URL 그대로"
           style="font-size:12px; color:#2563b0; text-decoration:underline;
                  text-underline-offset:2px; font-weight:500;">
          기사 원문 제목 그대로
        </a>

위 스펙 그대로 완전한 HTML 문서 출력. 수집된 20개 기사 모두 포함 필수."""

    print("📡 2단계: HTML 뉴스레터 생성 중...")
    result = call_gemini(system, user, max_tokens=16000, use_search=False)
    print("✅ 2단계 완료 — HTML 생성됨")
    return result


# ─── HTML 정제 ──────────────────────────────
def extract_html(raw: str) -> str:
    raw = re.sub(r"```html\s*|```\s*", "", raw, flags=re.IGNORECASE)
    m   = re.search(r"(<html[\s\S]*?</html>)", raw, re.IGNORECASE)
    return m.group(1).strip() if m else (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='UTF-8'></head>"
        "<body style='background:#fafaf8;padding:20px;max-width:680px;"
        "margin:auto;font-family:Noto Sans KR,sans-serif'>"
        f"{raw}</body></html>"
    )


# ─── Gmail 발송 ─────────────────────────────
def send_email(html: str, subject: str):
    msg             = MIMEMultipart("alternative")
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


# ─── 메인 ───────────────────────────────────
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

    # 1단계: 실제 기사 목록 수집
    articles = fetch_articles(today, yest)

    # 2단계: HTML 뉴스레터 생성
    raw_html = generate_html(today, articles)
    html     = extract_html(raw_html)

    # 발송
    subject = f"[{code}] 플랫폼 기획자 데일리 브리프 | {today}"
    send_email(html, subject)
    print(f"\n🎉 완료: {subject}\n")


if __name__ == "__main__":
    main()
