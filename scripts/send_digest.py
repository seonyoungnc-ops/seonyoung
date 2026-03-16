import smtplib
import os
import urllib.request
import json
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

today = datetime.now().strftime("%Y년 %m월 %d일")

# 1. 환경 변수 체크 (디버깅용)
api_key = os.environ.get("GEMINI_API_KEY")
send_to = os.environ.get("SEND_TO")
smtp_pw = os.environ.get("SMTP_PASSWORD")

if not api_key:
    print("❌ 에러: GEMINI_API_KEY 환경 변수가 없습니다. GitHub Secrets를 확인하세요.")
    exit(1)

# 2. URL 구성 (v1으로 고정)
model_name = "gemini-1.5-flash"
url = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={api_key}"

prompt = "오늘은 " + today + """입니다. IT 업계 플랫폼 기획자를 위한 전날 발행된 최신 기사를 아래 4개 카테고리별로 각 5개씩 정리해줘.
카테고리: 국내 게임 시장 / 글로벌 게임 시장 / IT 업계 / AI
결과는 인라인 CSS 포함한 깔끔한 White Tone HTML 뉴스레터로 출력해줘."""

data = json.dumps({
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"maxOutputTokens": 8000}
}).encode("utf-8")

html_content = None

# 3. API 호출
for attempt in range(3):
    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            result = json.loads(res.read())
        
        # HTML 추출 및 정제
        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
        html_content = raw_text.replace("```html", "").replace("```", "").strip()
        print(f"✅ API 호출 성공 (시도 {attempt + 1}회)")
        break
    except Exception as e:
        print(f"⚠️ 시도 {attempt + 1} 실패: {e}")
        if attempt < 2:
            time.sleep(5)
        else:
            raise

# 4. 메일 발송
if html_content:
    GMAIL = "seonyoung.ncsoft@gmail.com"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Daily IT Digest] {today} 오늘의 IT 뉴스"
    msg["From"] = GMAIL
    msg["To"] = send_to
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_
