import os
import requests
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

def send_newsletter():
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    now = datetime.now()
    limit_time = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    # 1. 사용 가능한 모델 리스트를 먼저 가져옵니다.
    print("🔍 사용 가능한 모델 리스트 확인 중...")
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        models_res = requests.get(list_url)
        if models_res.status_code != 200:
            print(f"❌ 모델 리스트 획득 실패: {models_res.status_code}")
            return

        # 'gemma'가 포함된 모델을 먼저 찾고, 없으면 'gemini-1.5-flash'를 찾습니다.
        model_list = [m['name'] for m in models_res.json().get('models', [])]
        target_model = next((m for m in model_list if 'gemma' in m), None)
        if not target_model:
            target_model = next((m for m in model_list if 'gemini-1.5-flash' in m), "models/gemini-1.5-flash")

        print(f"✅ 선택된 모델: {target_model}")

        # 2. 선택된 모델로 뉴스레터 생성
        prompt = f"""
        IT/게임 기획자로서 {limit_time} 이후 뉴스를 큐레이션하세요.
        - 분야: 국내게임, 국외게임, IT시장, AI변화 (총 12건)
        - 디자인: 보라색(#5c00d2) 헤더, 12px 폰트, HTML 표 형식
        - 출력: 순수 <html> 태그로만 응답
        """

        gen_url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        res = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=120)

        if res.status_code == 200:
            raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            clean_html = re.sub(r'```html|```', '', raw_text).strip()
            
            msg = MIMEMultipart()
            msg['From'] = smtp_email
            msg['To'] = target_email
            msg['Subject'] = f"[Daily Digest] {now.strftime('%Y-%m-%d')} IT/게임 동향"
            msg.attach(MIMEText(clean_html, 'html'))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, target_email, msg.as_string())
            print("✅ 메일 발송 완료!")
        else:
            print(f"❌ 생성 실패 (에러코드: {res.status_code})")
            print(f"상세내용: {res.text}")

    except Exception as e:
        print(f"⚠️ 시스템 오류: {e}")

if __name__ == "__main__":
    send_newsletter()
