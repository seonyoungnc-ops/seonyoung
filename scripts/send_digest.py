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

    # 1. 모델 리스트 확인 (가장 단순하고 안전한 주소 방식)
    print("🔍 모델 리스트 확인 중...")
    try:
        models_res = requests.get("https://generativelanguage.googleapis.com/v1beta/models?key=" + api_key)
        model_list = [m['name'] for m in models_res.json().get('models', [])]
        target_model = next((m for m in model_list if 'gemma' in m), "models/gemini-1.5-flash")
        print(f"✅ 선택된 모델: {target_model}")

        # 2. 프롬프트 (보라색 테마 + 인사이트 중심)
        prompt = f"""
        당신은 NCSOFT 전략 기획팀 플래너입니다. 아래 지시를 엄격히 따르십시오.
        
        [보고서 구성]
        분야: [국내 게임], [국외 게임], [AI 시장], [IT 시장] (각 5개씩 총 20개)

        [작성 형식]
        - [제목]: 뉴스 제목
        - 요약: 핵심 내용 1줄 요약
        - 원문 Link: <a href='URL' style='color:#5c00d2;'>원문 보러가기</a>
        - 주목해야 하는 이유: 기획자적 관점의 인사이트 (3줄 이상 상세히)

        [디자인 가이드 - CS Report 이미지 테마]
        - 전체 배경(#5c00d2) / 카드(흰색, 둥근 모서리, 회색 테두리) / 폰트(12px, Sans-serif)
        
        [출력 규칙]
        - <html>로 시작해 </html>로 끝나는 순수 HTML만 응답할 것. (설명, 마크다운 금지)
        """

        # 3. API 호출 (문자열 조립으로 어댑터 에러 완전 방지)
        url = "https://generativelanguage.googleapis.com/v1beta/" + target_model + ":generateContent?key=" + api_key
        
        print(f"🚀 생성 요청 중... {target_model}")
        res = requests.post(
            url, 
            json={"contents": [{"parts": [{"text": prompt}]}]}, 
            timeout=180
        )

        if res.status_code == 200:
            raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            
            # HTML 추출 및 배경색 강제 적용
            html_match = re.search(r'(<html.*</html>)', raw_text, re.DOTALL | re.IGNORECASE)
            clean_html = html_match.group(1) if html_match else re.sub(r'```html|```', '', raw_text).strip()
            
            if not clean_html.startswith('<html'):
                clean_html = f"<html><body style='background-color:#5c00d2; padding:20px; font-family:sans-serif;'>{clean_html}</body></html>"

            # 4. 메일 발송
            msg = MIMEMultipart()
            msg['From'] = smtp_email
            msg['To'] = target_email
            msg['Subject'] = f"[{now.strftime('%m%d')}] Insight Intelligence Report"
            msg.attach(MIMEText(clean_html, 'html'))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, target_email, msg.as_string())
            print("✅ 메일 발송 완료!")
        else:
            # 429 에러가 발생하면 상세 메시지 출력
            print(f"❌ 생성 실패: {res.status_code}, {res.text}")

    except Exception as e:
        print(f"⚠️ 시스템 오류: {e}")

if __name__ == "__main__":
    send_newsletter()
