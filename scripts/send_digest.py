import os
import requests
import json
import smtplib
import re
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def send_digest():
    # 1. 환경 변수 로드
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    if not all([api_key, smtp_email, smtp_password]):
        print("❌ 오류: 환경 변수 설정을 확인하세요.")
        return

    today = datetime.now().strftime("%Y년 %m월 %d일")
    prompt = f"오늘은 {today}입니다. 한국/글로벌 게임, IT, AI 분야 최신 뉴스 5개씩 IT 기획자를 위한 HTML 뉴스레터로 작성해줘. <html><body> 포함, 마크다운 기호 제외."

    # 2. 모델 리스트
    model_list = ["gemini-1.5-flash", "gemini-1.5-flash-latest"]
    raw_text = None
    
    for model in model_list:
        # ❗ 중요: URL에 대괄호나 링크 기호가 절대 섞이지 않도록 문자열을 직접 합칩니다.
        host = "https://generativelanguage.googleapis.com"
        path = f"/v1beta/models/{model}:generateContent"
        url = host + path + "?key=" + api_key
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        try:
            print(f"📡 모델 시도 중: {model}...")
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print(f"✅ {model} 호출 성공!")
                break
            else:
                print(f"⚠️ {model} 실패: {response.status_code}")
                continue
        except Exception as e:
            print(f"⚠️ 에러 발생: {e}")
            continue

    if not raw_text:
        print("❌ 모든 모델 호출 실패. 주소 형식을 다시 확인하세요.")
        return

    # 3. 이메일 전송
    try:
        clean_html = re.sub(r'```html|```', '', raw_text).strip()
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = target_email
        msg['Subject'] = f"[Daily Digest] {today} IT/게임 산업 동향 리포트"
        msg.attach(MIMEText(clean_html, 'html'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, target_email, msg.as_string())
        
        print(f"✅ 뉴스레터 발송 성공! ({target_email})")
    except Exception as e:
        print(f"⚠️ 이메일 전송 실패: {e}")

if __name__ == "__main__":
    send_digest()
