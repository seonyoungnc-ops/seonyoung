import anthropic, smtplib, os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
today = datetime.now().strftime("%Y년 %m월 %d일")

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8000,
    messages=[{
        "role": "user",
        "content": f"""오늘은 {today}입니다. IT 업계 플랫폼 기획자를 위한 전날 발행된 최신 기사를 아래 4개 카테고리별로 각 5개씩 정리해줘.

카테고리: 국내 게임 시장 / 글로벌 게임 시장 / IT 업계 / AI

각 기사 형식:
[제목] (#키워드)
- 내용 요약
- 핵심 인사이트 (플랫폼 기획자 관점)
- 주목 사유
- 링크 (원문 URL)

결과는 인라인 CSS 포함한 깔끔한 White Tone HTML 뉴스레터로 출력해줘."""
    }]
)

html_content = message.content[0].text

GMAIL = "seonyoung@ncsoft.com"  # ← 수정

msg = MIMEMultipart('alternative')
msg['Subject'] = f"[Daily IT Digest] {today} 오늘의 IT 뉴스"
msg['From'] = GMAIL
msg['To'] = os.environ["SEND_TO"]
msg.attach(MIMEText(html_content, 'html'))

with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
    server.login(GMAIL, os.environ["SMTP_PASSWORD"])
    server.send_message(msg)

print("✅ 발송 완료!")
