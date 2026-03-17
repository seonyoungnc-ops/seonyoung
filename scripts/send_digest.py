import os
import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import re

def send_digest():
    """
    IT 플랫폼 기획자를 위한 일일 뉴스레터 자동 발송 스크립트
    분야: 한국 게임, 글로벌 게임, IT 시장, AI 변화 (각 5개씩)
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
    
    # 3. 프롬프트 구성 (분야 지정 및 5개씩 추출 요청)
    prompt = f"""
    오늘은 {today}입니다. 아래 4가지 분야에 대해 각각 '최신 뉴스 5개씩'을 선정하여 
    IT 플랫폼 기획자를 위한 전문적인 HTML 뉴스레터를 작성해줘.

    [핵심 요약 분야]
    1. 한국 게임 시장 (신작 소식, 규제 변화, 국내 주요 기업 동향)
    2. 글로벌 게임 시장 (콘솔/PC 트렌드, 해외 퍼블리싱, 글로벌 플랫폼 이슈)
    3. IT 시장 (빅테크 플랫폼 서비스, 모바일/웹 생태계 트렌드)
    4. AI 변화 (LLM 신기술, 생성형 AI 산업 적용 사례, 신규 툴 출시)

    [작성 가이드라인]
    - 각 분야별로 중요도가 높은 뉴스를 반드시 '5개씩' 엄선할 것. (총 20개 내외)
    - 각 항목은 [제목], [1~2문장의 핵심 요약], [관련 링크(실제 또는 예시)]를 포함할 것.
    - 디자인: 
        * 배경색: #f4f4f4
        * 본문 카드: #ffffff (둥근 모서리 적용)
        * 강조색(제목): #003366 (Deep Blue - NC소프트 느낌)
    - 반드시 <html><body> 태그를 포함한 '완전한 HTML 구조'로만 응답할 것.
    - 응답에 마크다운 코드 블록 기호(```html 또는 ```)를 절대 포함하지 마. 
    - 텍스트 중간에 마크다운 기호를 섞지 말고 순수 HTML 태그로만 구성해줘.
    """

    # 4. Gemma API 호출 (안정적인 12b 모델 사용)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-12b-it:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        print(f"🚀 {today} 뉴스레터 생성 시작 (모델: gemma-3-12b-it)...")
        # 응답 생성을 위해 넉넉하게 120초 타임아웃 설정
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # 🧹 HTML 찌꺼기 제거 및 정제 로직
            # 1. 시작 부분의 ```html 또는 ``` 제거
            clean_html = re.sub(r'^
