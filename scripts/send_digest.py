import smtplib
import os
import urllib.request
import json
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

today = datetime.now().strftime("%Y년 %m월 %d일")

prompt = "오늘은 " + today + """입니다. IT 업계 플랫폼 기획자를 위한 전날 발행된 최신 기사를 아래 4개 카테고리별로 각 5개씩 정리해줘.

카테고리: 국내 게임 시장 / 글로벌 게임 시장 / IT 업계 / AI

각 기사 형식:
[제목] (#키워드)
- 내용 요약
- 핵심 인사이트 (플랫폼 기획자 관점)
- 주목 사유
- 링크 (원문 URL)

결과는 인라인 CSS 포함한 깔끔한 White Tone HTML 뉴스레터로 출력해줘."""

api_key = os.environ["GEMINI_API_KEY"]
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + api_key

data = json.dumps({
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"maxOutputTokens": 8000}
}).encode("utf-8")

html_content = None

for attempt in range(3):
    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            result = json.loads(res.read())
        html_content = result["candidates"][0]["content"]["parts"][0]["text"]
        print("API 호출 성공 시도 " + str(attempt + 1) + "회")
        break
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("429 에러 60초 후 재시도 " + str(attempt + 1) + "/3")
            time.sleep(60)
        else:
            raise

if not html_content:
    raise Exception("API 호출 3회 모두 실패")

GMAIL = "seonyoung.ncsoft@gmail.com"

msg = MIMEMultipart("alternative")
msg["Subject"] = "[Daily IT Digest] " + today + " 오늘의 IT 뉴스"
msg["From"] = GMAIL
msg["To"] = os.environ["SEND_TO"]
msg.attach(MIMEText(html_content, "html"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL, os.environ["SMTP_PASSWORD"])
    server.send_message(msg)

print("메일 발송 완료!")
