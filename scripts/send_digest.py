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

    # 1. 모델 리스트 확인 및 모델 선택
    print("🔍 사용 가능한 모델 리스트 확인 중...")
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    try:
        models_res = requests.get(list_url)
        model_list = [m['name'] for m in models_res.json().get('models', [])]
        # Gemma 우선 선택, 없으면 Flash
        target_model = next((m for m in model_list if 'gemma' in m), "models/gemini-1.5-flash")
        print(f"✅ 선택된 모델: {target_model}")

        # 2. 기획자 맞춤형 인라인 스타일 프롬프트
        prompt = f"""
        당신은 NCSOFT 전략 기획팀 플래너입니다. {limit_time} 이후 동향을 보고하세요.
        분야: [국내 게임], [국외 게임], [AI 시장], [IT 시장] (각 5개씩 총 20개)

        각 항목 작성 형식:
        - [제목]: 뉴스 제목
        - 요약: 핵심 내용 1줄
        - 원문 Link: 실제 URL (https://... 형식 필수)
        - 주목해야 하는 이유: 기획자적 관점의 인사이트 (2~3줄)

        디자인: 
        - 배경색 #5c00d2 헤더, 흰색 카드 레이아웃, 12px 폰트.
        - 반드시 <html> 태그로 시작하고 끝나는 순수 HTML만 응답하세요. 설명이나 마크다운은 금지합니다.
        """

        # 3. API 호출 (이 부분에서 res가 정의됩니다)
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        res = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=180)

        if res.status_code == 200:
            raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            print("✅ 본문 생성 성공!")

            # HTML 추출 로직
            html_match = re.search(r'(<html.*</html>)', raw_text, re.DOTALL | re.IGNORECASE)
            clean_html = html_match.group(1) if html_match else re.sub(r'```html|```', '', raw_text).strip()
            
            # 메일 발송
            msg = MIMEMultipart()
            msg['From'] = smtp_email
            msg['To'] = target_email
            msg['Subject'] = f"[Insight Digest] {now.strftime('%Y-%m-%d')} IT 시장 리포트"
            msg.attach(MIMEText(clean_html, 'html'))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, target_email, msg.as_string())
            print("✅ 메일 발송 완료!")
        else:
            print(f"❌ 생성 실패: {res.status_code}, {res.text}")

    except Exception as e:
        print(f"⚠️ 시스템 오류: {e}")

if __name__ == "__main__":
    send_newsletter()
