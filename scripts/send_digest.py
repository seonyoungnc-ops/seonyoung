import smtplib
import os
import requests
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# 1. 환경 변수 로드
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
smtp_pw = os.environ.get("SMTP_PASSWORD", "").strip()
send_to = os.environ.get("SEND_TO", "seonyoung@ncsoft.com").strip()

# 2. API 설정 (리스트에서 확인된 gemini-2.0-flash 사용)
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

today = datetime.now().strftime("%Y년 %m월 %d일")
prompt = f"오늘은 {today}입니다. IT 플랫폼 기획자를 위한 오늘의 주요 기술 뉴스들을 카테고리별로 요약해서 깔끔한 HTML 뉴스레터 형식으로 작성해줘."

payload = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {
        "maxOutputTokens": 4096,
        "temperature": 0.7
    }
}

# 3. API 호출
try:
    response = requests.post(url, json=payload, timeout=60)
    if response.status_code == 200:
        result = response.json()
        html_content = result["candidates"][0]["content"]["parts"][0]["text"]
        # 마크다운 태그 제거
        html_content = html_content.replace("```html", "").replace("```", "").strip()
        print("✅ Gemini API 호출 성공!")
    else:
        print(f"❌ API 에러: {response.status_code}")
        print(response.text)
        exit(1)

    # 4. 메일 발송 로직
    GMAIL_USER = "seonyoung.ncsoft@gmail.com"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Daily IT Digest] {today} 오늘의 IT 뉴스"
    msg["From"] = GMAIL_USER
    msg["To"] = send_to
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, smtp_pw)
        server.send_message(msg)
    print("🚀 뉴스레터 발송 완료!")

except Exception as e:
    print(f"❌ 오류 발생: {e}")
    exit(1)
