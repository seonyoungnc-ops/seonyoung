import os
import requests
import json
import smtplib
import re
import time
import schedule
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

def task():
    """뉴스레터 생성 및 발송 핵심 로직"""
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    limit_time = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    # [기획자 요구사항] 4개 분야 x 5개씩 = 총 20개
    prompt = f"""
    당신은 IT/게임 전략 기획자입니다. {limit_time} 이후 24시간 내 뉴스를 큐레이션하세요.
    - 분야별 5개씩(총 20개): 1.국내게임 2.국외게임 3.IT시장 4.AI변화
    - 항목: [제목], [1~2문장 요약], [링크]
    - 디자인: #f4f4f4 배경, #ffffff 카드형 HTML (순수 HTML로만 응답)
    """

    # 주소 오염 방지 조립
    u = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    print(f"🚀 [{datetime.now().strftime('%H:%M:%S')}] 뉴스레터 생성 시작...")

    raw_text = None
    # 429 에러 발생 시 최대 3번 재시도 (각 2분 간격)
    for i in range(3):
        try:
            res = requests.post(u, params={'key': api_key}, 
                                json={"contents": [{"parts": [{"text": prompt}]}]}, 
                                timeout=120)
            if res.status_code == 200:
                raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                break
            elif res.status_code == 429:
                print(f"⏳ 할당량 초과. 120초 후 재시도... ({i+1}/3)")
                time.sleep(120)
            else:
                print(f"❌ API 오류: {res.status_code}")
                break
        except Exception as e:
            print(f"⚠️ 연결 오류: {e}")
            time.sleep(10)

    if raw_text:
        try:
            clean_html = re.sub(r'```html|```', '', raw_text).strip()
            msg = MIMEMultipart()
            msg['From'] = smtp_email
            msg['To'] = target_email
            msg['Subject'] = f"[Daily Digest] {today_str} IT/게임 최신 동향 (20건)"
            msg.attach(MIMEText(clean_html, 'html'))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, target_email, msg.as_string())
            print(f"✅ 발송 성공! ({target_email})")
        except Exception as e:
            print(f"⚠️ 발송 실패: {e}")
    else:
        print("❌ 본문 생성 실패로 발송을 건너뜁니다.")

# --- 스케줄러 설정 ---
# 매일 오전 09:00에 실행되도록 설정
schedule.every().day.at("09:00").do(task)

print("📅 뉴스레터 자동 발송 시스템 가동 중... (매일 오전 9시)")
# 테스트를 위해 즉시 한 번 실행하려면 아래 줄의 주석을 해제하세요.
# task() 

while True:
    schedule.run_pending()
    time.sleep(60) # 1분마다 체크
