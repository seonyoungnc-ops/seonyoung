"""
Platform Planner Daily Brief
────────────────────────────────────────
Claude API로 24시간 이내 기사를 수집·요약해
White Tone HTML 뉴스레터를 Gmail로 자동 발송합니다.
매일 09:00 KST (GitHub Actions 00:00 UTC) 실행
"""

import os, re, smtplib, sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import anthropic

# ─── 환경변수 ───────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SMTP_EMAIL        = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD     = os.environ.get("SMTP_PASSWORD", "")
TARGET_EMAIL      = os.environ.get("TARGET_EMAIL", "seonyoung@ncsoft.com")
KST               = timezone(timedelta(hours=9))


# ─── 1. 시스템 프롬프트 ─────────────────────
SYSTEM_PROMPT = """당신은 IT 업계 10년 차 플랫폼 기획 전문가입니다.
매일 아침 동료 플랫폼/서비스 기획자를 위한 데일리 뉴스 브리프를 작성합니다.

[필수 규칙]
1. 반드시 실제로 존재하는 신뢰할 수 있는 매체의 기사만 사용
   (게임메카, 인벤, 루리웹, 이코리아, 전자신문, ZDNet,
    TechCrunch, Polygon, gamesindustry.biz, Wired 등)
2. 존재하지 않거나 확신이 없는 기사는 절대 사용 금지
3. URL은 반드시 실제 접근 가능한 직접 기사 링크
4. 순수 HTML만 출력 (<html>로 시작, </html>로 종료)"""


# ─── 2. 유저 프롬프트 빌더 ──────────────────
def build_prompt(today: str, yesterday: str) -> str:
    return f"""오늘 날짜: {today} (KST)
수집 기사 범위: {yesterday} 00:00 ~ {today} 09:00 (24시간 이내)

카테고리별 각 5개씩, 총 20개 기사 수집·요약:
1. 🎮 국내 게임 시장  2. 🌐 글로벌 게임 시장
3. 💻 IT 업계          4. 🤖 AI

각 기사 형식:
- 제목(키워드 태그 포함) / 내용(2-3문장) / 요약(1줄)
- 주목해야 하는 사유(플랫폼 기획자 관점, 구체적으로 2-3문장)
- 링크(실제 원문 URL)

디자인 스펙 (오늘 생성된 브리프와 동일하게):
- 배경 #fafaf8 / 카드 #ffffff / 테두리 #e8e6e0 / border-radius 10px
- 헤더폰트: DM Serif Display / 본문: Noto Sans KR / 라벨: JetBrains Mono
- 국내게임 #c84b31 / 글로벌게임 #2563b0 / IT #7c3aed / AI #0891b2
- row-label 그리드 레이아웃 (내용/요약/주목/링크) / 최대 너비 780px
- Google Fonts CDN 임포트 필수 포함
- 완전한 HTML 문서로 출력"""


# ─── 3. Claude API 호출 ─────────────────────
def generate_brief(today: str, yesterday: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    print("📡 Claude API 호출 중...")

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(today, yesterday)}],
    )
    tok = msg.usage
    print(f"✅ 완료 (입력 {tok.input_tokens} / 출력 {tok.output_tokens} 토큰)")
    return msg.content[0].text


# ─── 4. HTML 정제 ───────────────────────────
def extract_html(raw: str) -> str:
    raw = re.sub(r"```html\s*|```\s*", "", raw, flags=re.IGNORECASE)
    m   = re.search(r"(<html[\s\S]*?</html>)", raw, re.IGNORECASE)
    return m.group(1).strip() if m else (
        f"<!DOCTYPE html><html lang='ko'><head>"
        f"<meta charset='UTF-8'></head>"
        f"<body style='font-family:Noto Sans KR,sans-serif;"
        f"background:#fafaf8;padding:20px;max-width:780px;margin:auto'>"
        f"{raw}</body></html>"
    )


# ─── 5. Gmail 발송 ──────────────────────────
def send_email(html: str, subject: str):
    msg                = MIMEMultipart("alternative")
    msg["From"]       = SMTP_EMAIL
    msg["To"]         = TARGET_EMAIL
    msg["Subject"]    = subject
    msg.attach(MIMEText("HTML 지원 클라이언트에서 확인하세요.", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    print(f"📧 발송 중 → {TARGET_EMAIL}")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SMTP_EMAIL, SMTP_PASSWORD)
        s.sendmail(SMTP_EMAIL, TARGET_EMAIL, msg.as_string())
    print("✅ 발송 완료!")


# ─── 6. 메인 ────────────────────────────────
def main():
    now   = datetime.now(KST)
    today = now.strftime("%Y년 %m월 %d일")
    yest  = (now - timedelta(days=1)).strftime("%Y년 %m월 %d일")
    code  = now.strftime("%m%d")

    print(f"\n🗓  {today} 데일리 브리프 시작\n{'─'*48}")

    for v, n in [(ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY"),
                  (SMTP_EMAIL,        "SMTP_EMAIL"),
                  (SMTP_PASSWORD,     "SMTP_PASSWORD")]:
        if not v:
            print(f"❌ 환경변수 미설정: {n}"); sys.exit(1)

    html    = extract_html(generate_brief(today, yest))
    subject = f"[{code}] 플랫폼 기획자 데일리 브리프 | {today}"
    send_email(html, subject)
    print(f"\n🎉 완료: {subject}\n")


if __name__ == "__main__":
    main()
