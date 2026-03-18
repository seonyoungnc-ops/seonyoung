import os
import requests
import json
import smtplib
import re
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

def send_newsletter():
    # 1. 환경 변수 로드
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    if not all([api_key, smtp_email, smtp_password]):
        print("❌ 오류: 환경 변수 설정을 확인해주세요.")
        return

    # 2. 시간 설정 (24시간 이내 강조)
    today = datetime.now().strftime("%Y-%m-%d")
    limit_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    # 3. [기획자 요구사항] 프롬프트 최적화
    prompt = f"""
    당신은 IT/게임 전문 기획자입니다. 기준시점({limit_time}) 이후 24시간 내 뉴스를 큐레이션하세요.
    
    [필수 포함 내용]
    - 분야: 국내게임, 국외게임, IT시장, AI (각 5개씩 총 20개)
    - 형식: [제목], [1~2문장 요약], [링크]
    - 디자인: 배경 #f4f4f4, 카드 #ffffff, 제목색 #003366의 깔끔한 HTML
    - 주의: 마크다운(```) 없이 <html> 태그로만 응답할 것.
    """

    # 4. API 설정 (가장 안정적인 v1beta 사용)
    url = "[https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent](https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent)"
    
    print(f"🚀 {today} 뉴스레터 생성 시작 (24시간 이내 소식 20건)...")

    raw_text = None
    for i in range(3):
        try:
            # params를 통해 API 키 전달 (가장 안전한 방식)
            response = requests.post(url, params={'key': api_key}, 
                                     json={"contents": [{"parts": [{"text": prompt}]}]}, 
                                     timeout=150) # 시간 충분히 부여
            
            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print("✅ 본문 생성 완료!")
                break
            elif response.status_code == 429:
                # 무료 플랜의 핵심: 에러 시 아예 길게 쉬어야 합니다.
                wait = 120 * (i + 1)
                print(f"⏳ 할당량 초과. {wait}초 후 강제 재시도... ({i+1}/3)")
                time.sleep(wait)
            else:
                print(f"❌ API 에러 ({response.status_code}): {response.text}")
                break
        except Exception as e:
            print(f"⚠️ 연결 오류: {e}")
            time.sleep(10)

    if not raw_text:
        print("❌ 실패: 할당량이 회복되지 않았습니다. 10분 뒤에 다시 시도하세요.")
        return

    # 5. 이메일 발송
    try:
        clean_html = re.sub(r'```html|```', '', raw_text).strip()
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = target_email
        msg['Subject'] = f"[Daily Digest] {today} IT/게임 최신 동향"
        msg.attach(MIMEText(clean_html, 'html'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, target_email, msg.as_string())
        print(f"✅ 뉴스레터 발송 성공! ({target_email})")
    except Exception as e:
        print(f"⚠️ 발송 실패: {e}")

if __name__ == "__main__":
    send_newsletter()
