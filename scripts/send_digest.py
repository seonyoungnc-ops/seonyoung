import smtplib, os, urllib.request, json, time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

today = datetime.now().strftime("%Y년 %m월 %d일")

prompt = f"""오늘은 {today}입니다. IT 업계 플랫폼 기획자를 위한 전날 발행된 최신 기사를 아래 4개 카테고리별로 각 5개씩 정리해줘.

카테고리: 국내 게임 시장 / 글로벌 게임 시장 / IT 업계 / AI

각 기사 형식:
[제목] (#키워드)
- 내용 요약
- 핵심 인사이트 (플랫폼 기획자 관점)
- 주목 사유
- 링크 (원문 URL)

결과는 인라인 CSS 포함한 깔끔한 White Tone HTML 뉴스레터로 출력해줘."""

api_key = os.environ["GEMINI_API_KEY"]
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"

data = json.dumps({
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"maxOutputTokens": 8000}
}).encode("utf-8")

html_content = None
for attempt in range(3):
    try:
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            result = json.loads(res.read())
