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
        print("❌ 오류: 환경 변수(API_KEY 등)가 설정되지 않았습니다.")
        return

    today = datetime.now().strftime("%Y년 %m월 %d일")
    prompt = f"{today} IT/게임/AI 분야 뉴스레터를 HTML로 작성해줘. 마크다운 기호 없이 <html> 태그로만 응답해."

    # 2. 가장 확실한 모델 및 경로 리스트
    # v1(안정판) 경로를 먼저 시도합니다.
    attempts = [
        {"version": "v1", "model": "gemini-1.5-flash"},
        {"version": "v1beta", "model": "gemini-1.5-flash"},
        {"version": "v1beta", "model": "gemini-2.0-flash"}
    ]

    raw_text = None
    
    for item in attempts:
        ver = item["version"]
        mod = item["model"]
        url = f"https://generativelanguage.googleapis.com/{ver}/models/{mod}:generateContent?key={api_key}"
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        try:
            print(f"📡 시도 중: {mod} ({ver} 경로)...")
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print(f"✅ {mod} 호출 성공!")
                break
            else:
                print(f"⚠️ {mod} ({ver}) 실패: {response.status_code}")
                continue
        except Exception as e:
            print(f"⚠️ 연결 에러: {e}")
            continue

    if not raw_text:
        print("❌ 모든 시도가 실패했습니다. API 키의 활성화 상태를 확인해주세요.")
        return

    # 3. 이메일 발송
    try:
        clean_html = re.sub(r'```html|```', '', raw_text).strip()
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = target_email
        msg['Subject'] = f"[Daily Digest] {today} IT 산업 리포트"
        msg.attach(MIMEText(clean_html, 'html'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, target_email, msg.as_string())
        print(f"✅ 뉴스레터 발송 완료! ({target_email})")
    except Exception as e:
        print(f"⚠️ 이메일 전송 실패: {e}")

if __name__ == "__main__":
    send_newsletter()
