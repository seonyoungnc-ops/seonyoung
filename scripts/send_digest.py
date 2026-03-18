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
    # 1. 환경 변수 로드 (원래 방식: 시스템 환경변수 사용)
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    if not all([api_key, smtp_email, smtp_password]):
        print("❌ 오류: 환경 변수(API_KEY, SMTP 설정 등)를 확인해주세요.")
        return

    today = datetime.now().strftime("%Y년 %m월 %d일")
    prompt = f"""
    오늘은 {today}입니다. 아래 4개 분야의 최신 뉴스 5개씩을 HTML 뉴스레터로 작성해줘.
    [한국 게임, 글로벌 게임, IT 시장, AI 변화]
    - <html><body> 태그 포함, 마크다운(```) 제외.
    """

    # 2. 무료 플랜에서 가장 잘 되는 모델명 리스트
    # 최신 순서대로 배치했습니다.
    model_list = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro"
    ]

    raw_text = None
    
    # 3. 루프를 돌며 성공할 때까지 호출
    for model in model_list:
        # 무료 플랜은 v1beta 엔드포인트가 가장 안정적입니다.
        url = f"[https://generativelanguage.googleapis.com/v1beta/models/](https://generativelanguage.googleapis.com/v1beta/models/){model}:generateContent?key={api_key}"
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
                # 429 에러(할당량 초과) 발생 시 잠시 대기
                if response.status_code == 429:
                    print("⏳ 할당량 초과로 5초 후 재시도...")
                    time.sleep(5)
                continue
        except Exception as e:
            print(f"⚠️ 에러 발생: {e}")
            continue

    if not raw_text:
        print("❌ 모든 모델 호출 실패. API 키의 유효성을 다시 확인해주세요.")
        return

    # 4. 이메일 전송
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
