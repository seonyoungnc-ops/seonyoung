import os
import requests
import smtplib
import re
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def send_newsletter():
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    # 분야별 1개씩 총 4개만 요청 (부하 최소화)
    prompt = "오늘의 IT, 게임 최신 뉴스 4개만 제목과 링크 위주로 깔끔하게 HTML로 정리해줘."
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    print("🚀 초경량 모드로 뉴스 생성 시도 중...")

    try:
        # 요청 전 강제 휴식 (중요!)
        time.sleep(10)
        res = requests.post(url, params={'key': api_key}, 
                            json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
        
        if res.status_code == 200:
            raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            print("✅ [성공] 드디어 본문이 생성되었습니다!")
            
            # 발송 로직
            clean_html = re.sub(r'```html|```', '', raw_text).strip()
            msg = MIMEMultipart()
            msg['From'] = smtp_email
            msg['To'] = target_email
            msg['Subject'] = f"[Daily Digest] {datetime.now().strftime('%Y-%m-%d')} 뉴스 테스트"
            msg.attach(MIMEText(clean_html, 'html'))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, target_email, msg.as_string())
            print("✅ [성공] 메일함으로 발송 완료!")
        else:
            print(f"❌ [실패] 구글 서버 응답: {res.status_code}")
            print("💡 팁: API 키가 지쳤습니다. 1시간 뒤에 다시 시도해 주세요.")

    except Exception as e:
        print(f"⚠️ 오류 발생: {e}")

if __name__ == "__main__":
    send_newsletter()
