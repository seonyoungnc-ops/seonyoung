import smtplib
import os
import urllib.request
import json
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

today = datetime.now().strftime("%Y년 %m월 %d일")

# 1. 환경 변수 체크
api_key = os.environ.get("GEMINI_API_KEY")
send_to = os.environ.get("SEND_TO")
smtp_pw = os.environ.get("SMTP_PASSWORD")

if not api_key:
    print("❌ 에러: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
    exit(1)

# 2. API 설정 (v1 및 gemini-1.5-flash로 404 에러 방지)
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

# 3. API 호출 시도
for attempt in range(3):
    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            result = json.loads(res.read())
        
        # HTML 추출 및 마크다운 제거
        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
        html_content = raw_text.replace("```html", "").replace("```", "").strip()
        print(f"✅ API 호출 성공 (시도 {attempt + 1}회)")
        break
    except Exception as e:
        print(f"⚠️ 시도 {attempt + 1} 실패: {e}")
        if attempt < 2:
            time.sleep(10)
        else:
            print("❌ 모든 API 호출 시도가 실패했습니다.")
            exit(1)

# 4. 메일 발송
if html_content:
    GMAIL = "seonyoung.ncsoft@gmail.com"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Daily IT Digest] {today} 오늘의 IT 뉴스"
    msg["From"] = GMAIL
    msg["To"] = send_to
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL, smtp_pw)
            server.send_message(msg)
        print("🚀 메일 발송 성공!")
    except Exception as e:
        print(f"❌ 메일 발송 중 에러 발생: {e}")
