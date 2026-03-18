import os
import requests
import json
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

def send_newsletter():
    # 1. 새 환경 변수 로드
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    if not api_key or len(api_key) < 10:
        print("❌ 오류: 새 API 키가 정상적으로 설정되지 않았습니다.")
        return

    # 2. 날짜 설정 (24시간 내 최신 뉴스)
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    limit_time = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    # 3. 상세 프롬프트 (기획자 요구사항 완벽 반영)
    prompt = f"""
    당신은 IT/게임 전문 전략 기획자입니다. {limit_time} 이후 24시간 내 발생한 뉴스를 큐레이션하세요.
    
    [필수 항목]
    - 분야별 5개씩 (총 20개): 1.국내게임시장, 2.국외게임시장, 3.IT시장, 4.AI변화
    - 형식: [제목], [1~2문장 요약], [관련 링크]
    - 디자인: 배경 #f4f4f4, 카드 #ffffff, 제목색 #003366의 깔끔한 HTML
    - 주의: 마크다운(```) 없이 순수 <html> 태그로만 응답할 것.
    """

    # 4. API 호출 (오류 방지를 위해 주소 직접 입력)
    url = "[https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent](https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent)"
    
    print(f"🚀 새 API 키로 {today_str} 뉴스레터 생성 시작...")

    try:
        response = requests.post(
            url, 
            params={'key': api_key}, 
            json={"contents": [{"parts": [{"text": prompt}]}]}, 
            timeout=120
        )
        
        if response.status_code == 200:
            raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            print("✅ 뉴스레터 본문 생성 성공!")
            
            # 5. 이메일 발송
            clean_html = re.sub(r'```html|```', '', raw_text).strip()
            msg = MIMEMultipart()
            msg['From'] = smtp_email
            msg['To'] = target_email
            msg['Subject'] = f"[Daily Digest] {today_str} IT/게임 최신 동향 (20건)"
            msg.attach(MIMEText(clean_html, 'html'))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, target_email, msg.as_string())
            print(f"✅ 발송 완료! ({target_email})")
            
        else:
            print(f"❌ 실패 ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"⚠️ 연결 오류: {e}")

if __name__ == "__main__":
    send_newsletter()
