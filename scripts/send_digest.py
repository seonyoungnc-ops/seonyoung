import smtplib
import os
import urllib.request
import json
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# 1. 환경 변수 로드 (직접 확인)
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
smtp_pw = os.environ.get("SMTP_PASSWORD", "").strip()
send_to = os.environ.get("SEND_TO", "seonyoung@ncsoft.com").strip()

if not api_key:
    print("❌ 에러: GEMINI_API_KEY가 비어있습니다. GitHub Secrets를 확인하세요.")
    exit(1)

# 2. API 설정 (가장 안전한 v1beta 엔드포인트)
# f-string 대신 직접 더하기 방식으로 주소 오염 방지
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + api_key

today = datetime.now().strftime("%Y년 %m월 %d일")
prompt = f"오늘은 {today}입니다. IT 업계 플랫폼 기획자를 위한 최신 기사를 카테고리별로 정리해서 HTML 뉴스레터로 만들어줘."

data = json.dumps({
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"maxOutputTokens": 4096}
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
            # 안전하게 데이터 추출
            if "candidates" in result:
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                html_content = raw_text.replace("```html", "").replace("```", "").strip()
                print(f"✅ API 호출 성공 (시도 {attempt + 1})")
                break
    except Exception as e:
        print(f"⚠️ 시도 {attempt + 1} 실패: {e}")
        time.sleep(5)

# 4. 메일 발송
if html_content:
    GMAIL = "seonyoung.ncsoft@gmail.com"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Daily IT Digest] {today} 오늘의 IT 뉴스"
    msg["From"] = GMAIL
    msg["To"] = send_to
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL, smtp_pw)
        server.send_message(msg)
    print("🚀 메일 발송 완료!")
else:
    print("❌ 최종 실패: 생성된 내용이 없습니다.")
    exit(1)
