"""
Platform Planner Daily Brief — 네이버 뉴스 API + Gemini
1단계: 네이버 뉴스 API로 실제 기사 제목 + URL 수집
2단계: Gemini로 요약 + HTML 뉴스레터 생성
→ URL 100% 실제 기사 링크 보장
"""
import os, re, smtplib, sys, json
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib.request, urllib.parse

GEMINI_API_KEY      = os.environ.get("GEMINI_API_KEY", "")
NAVER_CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
SMTP_EMAIL          = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD       = os.environ.get("SMTP_PASSWORD", "")
TARGET_EMAIL        = os.environ.get("TARGET_EMAIL", "seonyoung@ncsoft.com")
KST                 = timezone(timedelta(hours=9))
MODEL               = "gemini-2.5-flash"

# 카테고리별 검색 키워드
CATEGORIES = {
    "🎮 국내 게임 시장": ["국내 게임 신작", "모바일 게임 출시", "게임 업계 뉴스"],
    "🌐 글로벌 게임 시장": ["글로벌 게임 시장", "콘솔 게임 해외", "게임 글로벌 출시"],
    "💻 IT 업계": ["IT 업계 뉴스", "플랫폼 서비스 출시", "빅테크 동향"],
    "🤖 AI": ["인공지능 AI 뉴스", "생성형 AI 서비스", "AI 플랫폼 기술"],
}


# ─── 1단계: 네이버 뉴스 API로 실제 기사 수집 ──
def search_naver_news(query: str, display: int = 5) -> list:
    """네이버 뉴스 검색 API 호출 → 기사 목록 반환"""
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display={display}&sort=date"
    req = urllib.request.Request(url, headers={
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    })
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode("utf-8"))
    return data.get("items", [])


def fetch_all_articles() -> str:
    """모든 카테고리 기사 수집 → Gemini에 넘길 텍스트 생성"""
    lines = []
    for category, keywords in CATEGORIES.items():
        lines.append(f"\n[{category}]")
        seen_titles = set()
        articles = []

        for keyword in keywords:
            try:
                items = search_naver_news(keyword, display=5)
                for item in items:
                    # HTML 태그 제거
                    title = re.sub(r"<[^>]+>", "", item["title"])
                    title = title.replace("&quot;", '"').replace("&amp;", "&")
                    # 중복 제거
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    # originallink 우선, 없으면 link 사용
                    url = item.get("originallink") or item.get("link", "")
                    desc = re.sub(r"<[^>]+>", "", item.get("description", ""))
                    articles.append({"title": title, "url": url, "desc": desc})
                    if len(articles) >= 5:
                        break
            except Exception as e:
                print(f"  ⚠️ {keyword} 검색 실패: {e}")
            if len(articles) >= 5:
                break

        for i, a in enumerate(articles[:5], 1):
            lines.append(f"{i}. 제목: {a['title']}")
            lines.append(f"   URL: {a['url']}")
            lines.append(f"   설명: {a['desc']}")
            lines.append("")

    return "\n".join(lines)


# ─── 2단계: Gemini로 HTML 생성 ──────────────
def generate_html(today: str, articles: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    system = """당신은 IT 업계 10년 차 플랫폼 기획 전문가입니다.
주어진 기사 목록을 바탕으로 HTML 뉴스레터를 생성합니다.
중요: 각 기사의 URL은 제공된 목록의 값을 절대 변경하지 말고 그대로 사용하십시오.
반드시 <html>로 시작해 </html>로 끝나는 순수 HTML만 출력하십시오."""

    user = f"""아래 기사 목록을 HTML 뉴스레터로 변환하십시오.
오늘 날짜: {today}

=== 수집된 기사 목록 (URL 절대 변경 금지) ===
{articles}
=============================================

각 기사마다:
- 내용: 기사 설명을 바탕으로 2-3문장 작성
- 요약: 핵심 1줄
- 주목사유: 플랫폼 기획자 관점 인사이트 2-3문장
- 키워드 태그: 3개

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

  링크: <a href="목록에서 제공된 URL 그대로"
           style="font-size:12px; color:#2563b0; text-decoration:underline;
                  text-underline-offset:2px; font-weight:500;">
          기사 제목 그대로
        </a>

위 스펙 그대로 완전한 HTML 문서 출력. 모든 기사 포함 필수."""

    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": 16000, "temperature": 0.5},
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    print("📡 Gemini HTML 생성 중...")
    with urllib.request.urlopen(req, timeout=180) as res:
        data = json.loads(res.read().decode("utf-8"))
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    print("✅ HTML 생성 완료")
    return text


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
    msg          = MIMEMultipart("alternative")
    msg["From"]  = SMTP_EMAIL
    msg["To"]    = TARGET_EMAIL
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
    code  = now.strftime("%m%d")

    print(f"\n🗓  {today} 데일리 브리프 시작\n{'─'*48}")
    for v, n in [(GEMINI_API_KEY,       "GEMINI_API_KEY"),
                 (NAVER_CLIENT_ID,      "NAVER_CLIENT_ID"),
                 (NAVER_CLIENT_SECRET,  "NAVER_CLIENT_SECRET"),
                 (SMTP_EMAIL,           "SMTP_EMAIL"),
                 (SMTP_PASSWORD,        "SMTP_PASSWORD")]:
        if not v:
            print(f"❌ 미설정: {n}"); sys.exit(1)

    # 1단계: 네이버 뉴스로 실제 기사 수집
    print("🔍 네이버 뉴스 API로 기사 수집 중...")
    articles = fetch_all_articles()
    print("✅ 기사 수집 완료")

    # 2단계: Gemini로 HTML 생성
    raw_html = generate_html(today, articles)
    html     = extract_html(raw_html)

    # 발송
    subject = f"[{code}] 플랫폼 기획자 데일리 브리프 | {today}"
    send_email(html, subject)
    print(f"\n🎉 완료: {subject}\n")


if __name__ == "__main__":
    main()
