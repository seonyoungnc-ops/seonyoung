"""
Platform Planner Daily Brief
Gemini 2.5 Flash (무료) · Gmail 자동 발송 · 09:00 KST
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

SYSTEM_PROMPT = """당신은 IT 업계 10년 차 플랫폼 기획 전문가입니다.
반드시 실제 존재하는 신뢰할 수 있는 매체의 기사만 사용하십시오.
(게임메카, 인벤, 루리웹, 이코리아, 전자신문, ZDNet, TechCrunch, Wired 등)
존재하지 않거나 확신이 없는 기사는 절대 사용 금지.
반드시 <html>로 시작해 </html>로 끝나는 순수 HTML만 출력."""


def build_prompt(today: str, yesterday: str) -> str:
    return f"""오늘: {today} (KST) / 기사 범위: {yesterday} 00:00 ~ {today} 09:00

[출력 조건 — 반드시 준수]
- 4개 카테고리 × 각 5개 = 정확히 20개 기사 (누락 절대 금지)
- 카테고리: 🎮 국내 게임 시장 / 🌐 글로벌 게임 시장 / 💻 IT 업계 / 🤖 AI
- 각 기사: 제목(키워드 태그) / 내용(2-3문장) / 요약(1줄) / 주목사유(2-3문장) / 원문링크

[HTML 디자인 스펙 — 아래 CSS를 그대로 사용할 것]
전체 wrapper: max-width:680px; margin:0 auto; padding:20px; background:#fafaf8;
font-family: 'Noto Sans KR', sans-serif;

[헤더 영역]
h1 (날짜+제목): font-size:18px; font-weight:700; color:#1a1a18;
  text-align:left; margin-bottom:4px; (한 줄로 표시 — 줄바꿈 없도록 작게)
날짜 부제: font-size:11px; color:#a0a095; font-family:monospace;

[카테고리 섹션 헤더]
배경 있는 pill 형태로 표시:
  display:inline-flex; align-items:center; gap:8px;
  padding:6px 14px; border-radius:20px; font-size:13px; font-weight:700;
국내게임: background:#fef2ee; color:#c84b31;
글로벌게임: background:#eff6ff; color:#2563b0;
IT업계: background:#f5f3ff; color:#7c3aed;
AI: background:#ecfeff; color:#0891b2;
섹션 하단 구분선: border-bottom:2px solid (각 카테고리 컬러); margin-bottom:16px;

[기사 카드]
border:1px solid #e8e6e0; border-radius:10px; padding:16px 18px;
margin-bottom:10px; background:#ffffff;

[기사 제목]
font-size:13px; font-weight:700; color:#1a1a18; margin-bottom:10px;

[키워드 태그]
font-size:10px; padding:2px 7px; border-radius:12px; margin-right:4px;
(카테고리별 컬러 배경+텍스트)

[row 라벨/내용 그리드]
display:grid; grid-template-columns:44px 1fr; gap:6px; margin-bottom:6px;
라벨(내용/요약/주목/링크): font-size:10px; font-weight:700; color:#a0a095;
  font-family:monospace; letter-spacing:0.06em; text-transform:uppercase; padding-top:1px;
내용 텍스트: font-size:12px; color:#6b6b62; line-height:1.6;
요약 텍스트: font-size:12px; color:#1a1a18; font-weight:500; line-height:1.6;
주목 텍스트: font-size:12px; color:#6b6b62; line-height:1.6;
링크: font-size:11px; color:#4a7c59; text-decoration:none; font-weight:500;

[Google Fonts import — head 안에 포함]
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">

위 스펙을 반영한 완전한 HTML 문서를 출력하십시오.
20개 기사를 모두 포함해야 합니다. 누락되면 재출력이 필요합니다."""


def generate_brief(today: str, yesterday: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": build_prompt(today, yesterday)}]}],
        "generationConfig": {
            "maxOutputTokens": 16000,  # 20개 기사 충분히 커버
            "temperature": 0.5
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    print(f"📡 Gemini ({MODEL}) 호출 중...")
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
        "<body style='background:#fafaf8;padding:20px;max-width:680px;margin:auto;"
        "font-family:Noto Sans KR,sans-serif'>"
        f"{raw}</body></html>"
    )


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

    html    = extract_html(generate_brief(today, yest))
    subject = f"[{code}] 플랫폼 기획자 데일리 브리프 | {today}"
    send_email(html, subject)
    print(f"\n🎉 완료: {subject}\n")


if __name__ == "__main__":
    main()
