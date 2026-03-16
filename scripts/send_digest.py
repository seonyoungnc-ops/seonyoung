import smtplib
import os
import requests
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# 1. 환경 변수 확인 및 출력 (보안을 위해 일부 마스킹)
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
smtp_pw = os.environ.get("SMTP_PASSWORD", "").strip()
send_to = os.environ.get("SEND_TO", "").strip()

if not api_key:
    print("❌ 에러: GEMINI_API_KEY가 없습니다.")
    exit(1)

print(f"DEBUG: API Key가 로드되었습니다. (앞 4자리: {api_key[:4]}...)")

# 2. API 설정 (가장 표준적인 경로)
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + api_key

today = datetime.now().strftime("%Y년 %m월 %d일")
prompt = f"오늘은 {today}입니다. IT 플랫폼 기획자를 위한 뉴스레터를 HTML로 작성해줘."

payload = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"maxOutputTokens": 2048}
}

# 3. API 호출
try:
    response = requests.post(url, json=payload, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        html_content = result["candidates"][0]["content"]["parts"][0]["text"]
        html_content = html_content.replace("```html", "").replace("```", "").strip()
        print("✅ API 호출 성공!")
    else:
        # 여기가 핵심입니다. 구글이 왜 404를 내는지 이유를 로그에 찍습니다.
        print(f"❌ API 에러 발생! 상태 코드: {response.status_code}")
        print(f"에러 내용: {response.text}")
        exit(1)

except Exception as e:
    print(f"❌ 통신 에러: {e}")
    exit(1)

# 4. 메일 발송
GMAIL = "seonyoung.ncsoft@gmail.com"
msg = MIMEMultipart("alternative")
msg["Subject"] = f"[Daily IT Digest] {today} 오늘의 뉴스"
msg["From"] = GMAIL
msg["To"] = send_to
msg.attach(MIMEText(html_content, "html"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL, smtp_pw)
    server.send_message(msg)

print("🚀 메일 발송 완료!")
