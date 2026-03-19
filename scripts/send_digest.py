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

    # 1. 모델 리스트 확인
    print("🔍 모델 리스트 확인 중...")
    list_url = "https://generativelanguage.googleapis.com/v1beta/models"
    
    try:
        models_res = requests.get(list_url, params={'key': api_key})
        model_data = models_res.json()
        model_list = [m['name'] for m in model_data.get('models', [])]
        
        # Gemma 모델 우선 선택 (없으면 Flash)
        target_model = next((m for m in model_list if 'gemma' in m), "models/gemini-1.5-flash")
        print(f"✅ 선택된 모델: {target_model}")

        # 2. 프롬프트 (보라색 테마 + 기획자 맞춤 형식)
        prompt = f"""
        당신은 NCSOFT 전략 기획팀 플래너입니다. 아래 지시를 엄격히 따르십시오.
        
        [보고서 구성]
        분야: [국내 게임 시장], [국외 게임 시장], [AI 시장], [IT 시장] (각 5개씩 총 20개)

        [개별 항목 필수 형식]
        - [제목]: 뉴스 제목
        - 요약: 핵심 내용 1줄 요약
        - 원문 Link: <a href='URL' style='color:#5c00d2;'>원문 보러가기</a>
        - 주목해야 하는 이유: 기획자적 관점의 인사이트 (2줄 이내)

        [디자인 가이드 - CS Report 이미지 테마]
        - 전체 배경: #5c00d2 (진보라색)
        - 카드 디자인: 흰색 배경, 둥근 모서리, 회색 테두리, 카드 간 간격 배치
        - 폰트: 12px, Sans-serif
        
        [출력 규칙]
        - 반드시 <html>로 시작해 </html>로 끝나는 순수 HTML만 응답할 것.
        - 인사말, 설명, 마크다운(```), 'placeholder' 같은 단어 절대 금지.
        """

        # 3. API 호출 (주소 에러 방지를 위해 깔끔하게 정리)
        # f-string 내부에서 주소가 꼬이지 않도록 변수를 조합합니다.
        base_url = "[https://generativelanguage.googleapis.com/v1beta](https://generativelanguage.googleapis.com/v1beta)"
        gen_endpoint = f"{base_url}/{target_model}:generateContent"
        
        print(f"🚀 생성 요청 중... ({target_model})")
        res = requests.post(
            gen_endpoint, 
            params={'key': api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]}, 
            timeout=180
        )

        if res.status_code == 200:
            raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            
            # HTML 추출 (설명 문구 제거)
            html_match = re.search(r'(<html.*</html>)', raw_text, re.DOTALL | re.IGNORECASE)
            if html_match:
                clean_html = html_match.group(1)
            else:
                clean_html = re.sub(r'```html|```', '', raw_text).strip()
                if not clean_html.startswith('<'):
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
            print(f"❌ 생성 실패: {res.status_code}, {res.text}")

    except Exception as e:
        print(f"⚠️ 시스템 오류: {e}")

if __name__ == "__main__":
    send_newsletter()
