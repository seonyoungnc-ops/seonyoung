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
        print("❌ 오류: 환경 변수가 비어있습니다. 등록 상태를 확인하세요.")
        print(f"- GEMINI_API_KEY: {'설정됨' if api_key else '미설정'}")
        return

    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    # 3. 프롬프트 구성
    prompt = f"오늘은 {today}입니다. 한국 게임, 글로벌 게임, IT, AI 분야 최신 뉴스 5개씩 HTML 뉴스레터로 작성해줘."

    # 4. Gemini API 호출 (모델명: gemini-3-flash)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent?key={api_key}"
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        print(f"🚀 {today} 뉴스레터 생성 시작 (Gemini 3 Flash)...")
        
        # timeout을 30초로 줄이고, 명시적인 에러 처리를 추가합니다.
        response = requests.post(url, json=payload, timeout=30)
        
        # 응답 상태 확인
        response.raise_for_status() 
        
        result = response.json()
        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
        clean_html = re.sub(r'```html|```', '', raw_text).strip()
        
        # 5. 이메일 전송 로직
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = target_email
        msg['Subject'] = f"[Daily Digest] {today} IT/게임 산업 동향 리포트"
        msg.attach(MIMEText(clean_html, 'html'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, target_email, msg.as_string())
        
        print(f"✅ 뉴스레터 발송 성공! ({target_email})")

    except requests.exceptions.RequestException as e:
        print(f"❌ 네트워크/API 오류 발생: {e}")
    except Exception as e:
        print(f"⚠️ 기타 오류 발생: {e}")

if __name__ == "__main__":
    send_digest()
