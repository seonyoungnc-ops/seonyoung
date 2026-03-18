import os
import requests
import json
import smtplib
import re
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def send_newsletter():
    # 1. 환경 변수 로드
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    if not all([api_key, smtp_email, smtp_password]):
        print("❌ 오류: 환경 변수 설정을 확인해주세요.")
        return

    today = datetime.now().strftime("%Y년 %m월 %d일")
    prompt = f"{today} IT/게임/AI 뉴스레터를 HTML로 작성해줘. <html> 태그로만 응답해."

    # 2. [검증됨] 429 에러가 났던 바로 그 모델과 주소
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    raw_text = None
    
    # 3. 429 에러(할당량 초과) 발생 시 자동 재시도 로직 (무료 플랜 필수)
    print(f"🚀 {today} 뉴스레터 생성 시작 (gemini-2.0-flash)...")
    
    for i in range(3): # 최대 3번 재시도
        try:
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print("✅ API 호출 성공!")
                break
            elif response.status_code == 429:
                print(f"⏳ 할당량 초과(429). {10 * (i+1)}초 후 다시 시도합니다...")
                time.sleep(10 * (i+1)) # 점진적으로 대기 시간 증가
            else:
                print(f"❌ 오류 발생 ({response.status_code}): {response.text}")
                break
        except Exception as e:
            print(f"⚠️ 연결 에러: {e}")
            break

    if not raw_text:
        print("❌ 뉴스레터 생성에 실패했습니다.")
        return

    # 4. 이메일 발송
    try:
        clean_html = re.sub(r'```html|```', '', raw_text).strip()
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = target_email
        msg['Subject'] = f"[Daily Digest] {today} 산업 동향 리포트"
        msg.attach(MIMEText(clean_html, 'html'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, target_email, msg.as_string())
        print(f"✅ 발송 완료! ({target_email})")
    except Exception as e:
        print(f"⚠️ 이메일 발송 실패: {e}")

if __name__ == "__main__":
    send_newsletter()
