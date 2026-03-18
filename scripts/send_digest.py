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
        print("❌ 오류: 환경 변수(API_KEY, SMTP 설정 등)를 확인해주세요.")
        return

    # 2. 날짜 설정 (24시간 이내 최신성 확보)
    now = datetime.now()
    today_str = now.strftime("%Y년 %m월 %d일")
    time_limit = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    # 3. [기획자님 요구사항] 상세 프롬프트
    prompt = f"""
    당신은 IT/게임 전문 전략 기획자입니다. 오늘은 {today_str}입니다.
    반드시 기준 시점({time_limit}) 이후 최근 24시간 이내에 보도된 뉴스만을 엄선하여 아래 4가지 분야별로 각 5개씩, 총 20개의 항목을 포함한 HTML 뉴스레터를 작성하세요.

    [핵심 큐레이션 분야]
    1. 국내 게임 시장 (신작 소식, 규제 변화, 국내 주요 기업 동향)
    2. 국외 게임 시장 (글로벌 콘솔/PC 트렌드, 해외 퍼블리싱, 글로벌 플랫폼 이슈)
    3. IT 시장 (빅테크 플랫폼 서비스 변화, 모바일/웹 생태계 트렌드)
    4. AI 변화 (LLM 신기술, 생성형 AI 산업 적용 사례, 신규 AI 툴 출시)

    [작성 가이드라인]
    - 각 분야별로 중요도가 높은 뉴스를 반드시 '5개씩' 포함할 것 (총 20개).
    - 각 항목은 [제목], [1~2문장의 전문적인 핵심 요약], [관련 링크]를 포함할 것.
    - 디자인: 배경색 #f4f4f4, 본문 카드 #ffffff, 제목 강조색 #003366.
    - 반드시 <html><body> 태그를 포함한 '완전한 HTML 구조'로만 응답할 것.
    - 응답에 마크다운 코드 블록 기호(```html 또는 ```)를 절대 포함하지 마세요.
    """

    # 4. 모델 리스트 (가장 안정적인 순서)
    models = ["gemini-2.0-flash", "gemini-1.5-flash"]
    raw_text = None

    print(f"🚀 {today_str} 뉴스레터 생성 시작 (24시간 이내 소식 20건)...")

    for model_name in models:
        if raw_text: break
        
        # URL 주소를 변수로 합치지 않고 base_url과 params로 분리하여 기호 오류 원천 봉쇄
        base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        params = {'key': api_key}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        for i in range(3):
            try:
                # params 옵션을 사용하면 requests가 주소를 안전하게 자동 생성합니다.
                response = requests.post(base_url, params=params, json=payload, timeout=90)
                
                if response.status_code == 200:
                    result = response.json()
                    raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"✅ {model_name} 호출 성공!")
                    break
                elif response.status_code == 429:
                    wait_sec = 30 * (i + 1)
                    print(f"⏳ 할당량 초과. {wait_sec}초 후 다시 시도... ({i+1}/3)")
                    time.sleep(wait_sec)
                else:
                    print(f"⚠️ {model_name} 실패 ({response.status_code})")
                    break
            except Exception as e:
                print(f"⚠️ {model_name} 실행 중 에러: {e}")
                break

    if not raw_text:
        print("❌ 뉴스레터 생성 실패. API 키 권한이나 네트워크를 확인하세요.")
        return

    # 5. 이메일 발송
    try:
        clean_html = re.sub(r'```html|```', '', raw_text).strip()
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = target_email
        msg['Subject'] = f"[Daily Digest] {today_str} IT/게임 산업 최신 동향 (20건)"
        msg.attach(MIMEText(clean_html, 'html'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, target_email, msg.as_string())
        print(f"✅ 뉴스레터 발송 성공! ({target_email})")
    except Exception as e:
        print(f"⚠️ 이메일 발송 단계 오류: {e}")

if __name__ == "__main__":
    send_newsletter()
