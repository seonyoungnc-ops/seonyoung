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

    # 2. 날짜 및 시간 설정
    now = datetime.now()
    today_str = now.strftime("%Y년 %m월 %d일")
    time_limit = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    # 3. 상세 프롬프트 (요구사항 반영)
    prompt = f"""
    당신은 IT/게임 전문 전략 기획자입니다. 오늘은 {today_str}입니다.
    반드시 기준 시점({time_limit}) 이후 최근 24시간 이내에 보도된 뉴스만을 엄선하여 아래 4가지 분야별로 각 5개씩, 총 20개의 항목을 포함한 HTML 뉴스레터를 작성하세요.

    [핵심 분야]
    1. 국내 게임 시장 (신작, 규제, 기업 동향)
    2. 국외 게임 시장 (글로벌 트렌드, 해외 기업, 플랫폼 이슈)
    3. IT 시장 (빅테크, 모바일/웹 생태계)
    4. AI 변화 (LLM 기술, 생성형 AI 산업 적용, 신규 툴)

    [작성 조건]
    - 각 분야별 중요 뉴스 '5개씩' 포함 (총 20개).
    - 항목 구성: [제목], [1~2문장 핵심 요약], [관련 링크].
    - 디자인: 배경 #f4f4f4, 카드 #ffffff, 제목색 #003366의 HTML 구조.
    - 마크다운 기호(```) 없이 순수 <html> 태그로만 응답하세요.
    """

    # 4. 주소 기호 오류 원천 봉쇄 (문자열 강제 결합 방식)
    # 주소에 대괄호([])가 섞이지 않도록 조각내어 합칩니다.
    h = "https://"
    g = "generativelanguage.googleapis.com"
    v = "/v1beta/models/gemini-2.0-flash:generateContent"
    endpoint = h + g + v

    raw_text = None
    print(f"🚀 {today_str} 뉴스레터 생성 시작 (24시간 이내 소식 20건)...")

    # 5. 실행 (429 할당량 초과 대비 60초 대기 로직)
    for i in range(3):
        try:
            # params를 통해 API 키를 안전하게 전달
            response = requests.post(endpoint, params={'key': api_key}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print("✅ 뉴스레터 본문 생성 성공!")
                break
            elif response.status_code == 429:
                wait_sec = 60 * (i + 1)
                print(f"⏳ 할당량 초과. {wait_sec}초 후 다시 시도합니다... ({i+1}/3)")
                time.sleep(wait_sec)
            else:
                print(f"❌ API 오류 ({response.status_code}): {response.text}")
                break
        except Exception as e:
            print(f"⚠️ 연결 에러 발생: 주소 형식을 확인 중입니다.")
            # 에러 발생 시 주소를 강제로 다시 초기화해서 재시도
            endpoint = "[https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent](https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent)"
            time.sleep(5)

    if not raw_text:
        print("❌ 뉴스레터 생성 실패.")
        return

    # 6. 이메일 발송
    try:
        clean_html = re.sub(r'```html|```', '', raw_text).strip()
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = target_email
        msg['Subject'] = f"[Daily Digest] {today_str} IT/게임 최신 동향 (20건)"
        msg.attach(MIMEText(clean_html, 'html'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, target_email, msg.as_string())
        print(f"✅ 발송 성공! ({target_email})")
    except Exception as e:
        print(f"⚠️ 이메일 발송 단계 오류: {e}")

if __name__ == "__main__":
    send_newsletter()
