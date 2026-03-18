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
    """
    IT 플랫폼 기획자를 위한 일일 뉴스레터 자동 발송 스크립트
    모델: gemini-1.5-flash (가장 안정적인 버전)
    """
    # 1. 환경 변수 로드
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    # 환경 변수 체크
    if not all([api_key, smtp_email, smtp_password]):
        print("❌ 오류: GEMINI_API_KEY, SMTP_EMAIL, SMTP_PASSWORD 환경 변수를 확인해주세요.")
        return

    # 2. 오늘의 날짜 설정
    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    # 3. 프롬프트 구성
    prompt = f"""
    오늘은 {today}입니다. 아래 4가지 분야에 대해 각각 '최신 뉴스 5개씩'을 선정하여 
    IT 플랫폼 기획자를 위한 전문적인 HTML 뉴스레터를 작성해줘.

    [핵심 요약 분야]
    1. 한국 게임 시장 (신작 소식, 규제 변화, 국내 주요 기업 동향)
    2. 글로벌 게임 시장 (콘솔/PC 트렌드, 해외 퍼블리싱, 글로벌 플랫폼 이슈)
    3. IT 시장 (빅테크 플랫폼 서비스, 모바일/웹 생태계 트렌드)
    4. AI 변화 (LLM 신기술, 생성형 AI 산업 적용 사례, 신규 툴 출시)

    [작성 가이드라인]
    - 각 분야별로 중요도가 높은 뉴스를 반드시 '5개씩' 엄선할 것.
    - 각 항목은 [제목], [1~2문장의 핵심 요약], [관련 링크]를 포함할 것.
    - 디자인: 배경색 #f4f4f4, 본문 카드 #ffffff, 제목 강조색 #003366.
    - 반드시 <html><body> 태그를 포함한 '완전한 HTML 구조'로만 응답할 것.
    - 응답에 마크다운 코드 블록 기호(```html 또는 ```)를 절대 포함하지 마.
    """

    # 4. Gemini API 호출 (gemini-1.5-flash)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        print(f"🚀 {today} 뉴스레터 생성 시작 (gemini-1.5-flash)...")
        
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # HTML 찌꺼기 제거
            clean_html = re.sub(r'```html|```', '', raw_text).strip()
            
            # 5. 이메일 객체 생성
            msg = MIMEMultipart()
            msg['From'] = smtp_email
            msg['To'] = target_email
            msg['Subject'] = f"[Daily Digest] {today} IT/게임 산업 동향 리포트"

            # HTML 본문 추가
            msg.attach(MIMEText(clean_html, 'html'))

            # 6. SMTP 서버를 통한 발송 (Gmail 기준)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, target_email, msg.as_string())
            
            print(f"✅ 뉴스레터 발송 성공! ({target_email})")
        else:
            print(f"❌ API 호출 실패: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"⚠️ 실행 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    send_digest()
