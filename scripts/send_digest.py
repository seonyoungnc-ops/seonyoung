import os
import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import re

def send_digest():
    # 1. 환경 변수 로드
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    if not all([api_key, smtp_email, smtp_password]):
        print("❌ 필요한 환경 변수가 설정되지 않았습니다.")
        return

    # 2. 오늘의 날짜 및 분야 설정
    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    # 3. 프롬프트 구성 (분야 지정 및 5개씩 추출 요청)
    prompt = f"""
    오늘은 {today}입니다. 아래 4가지 분야에 대해 각각 '최신 뉴스 5개씩'을 선정하여 
    IT 플랫폼 기획자를 위한 전문적인 HTML 뉴스레터를 작성해줘.

    [분야]
    1. 한국 게임 시장
    2. 글로벌 게임 시장
    3. IT 시장 (플랫폼 및 서비스 중심)
    4. AI 변화 (신기술 및 트렌드)

    [작성 가이드라인]
    - 각 분야별로 중요도가 높은 뉴스 5개를 선정할 것.
    - 각 뉴스는 제목과 1~2문장의 핵심 요약, 그리고 관련 링크(예시 URL도 좋음)를 포함할 것.
    - 디자인: 배경은 #f4f4f4, 본문은 흰색(#ffffff) 카드 타입, 제목은 NC소프트의 신뢰감을 주는 다크 블루 계열(#003366)을 사용할 것.
    - 반드시 <html><body> 태그를 포함한 완전한 HTML 구조로 작성할 것.
    - 응답에 마크다운 코드 블록 기호(```html 또는 ```)를 절대 포함하지 마. 오직 HTML 태그로만 시작하고 끝내줘.
    """

    # 4. Gemma API 호출 (12b 모델 사용 및 타임아웃 120초)
    url = f"[https://generativelanguage.googleapis.com/v1beta/models/gemma-3-12b-it:generateContent?key=](https://generativelanguage.googleapis.com/v1beta/models/gemma-3-12b-it:generateContent?key=){api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        print(f"🚀 {today} 뉴스레터 생성 중 (Gemma-3-12b-it)...")
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # 🧹 HTML 찌꺼기 제거 (정규식 사용)
            clean_html = re.sub(r'
