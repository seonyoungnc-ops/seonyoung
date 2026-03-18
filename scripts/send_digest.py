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

    # 2. 날짜 및 시간 설정 (24시간 이내 강조)
    now = datetime.now()
    today_str = now.strftime("%Y년 %m월 %d일")
    time_limit = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    # 3. [기획자 요구사항 반영] 상세 프롬프트
    prompt = f"""
    당신은 IT/게임 전문 전략 기획자입니다. 오늘은 {today_str}입니다.
    반드시 기준 시점({time_limit}) 이후 최근 24시간 이내에 발생한 뉴스만을 사용하여 뉴스레터를 작성하세요.

    [작성 필수 조건]
    1. 다음 4가지 분야별로 가장 중요한 뉴스를 '각각 5개씩' 엄선할 것 (총 20개 항목):
       - 국내 게임 시장 (신작, 규제, 국내 기업 동향)
       - 국외 게임 시장 (글로벌 트렌드, 해외 기업, 플랫폼 이슈)
       - IT 시장 (빅테크, 모바일/웹 생태계)
       - AI 변화 (LLM 기술, 생성형 AI 산업 적용, 신규 툴)
    2. 각 뉴스 항목 구성: [제목], [1~2문장의 핵심 요약], [관련 링크]
    3. 디자인: 배경 #f4f4f4, 카드 #ffffff, 제목색 #003366의 깔끔한 HTML
    4. 응답 형식: 마크다운(```) 기호 없이 오직 <html>로 시작하는 순수 HTML만 응답하세요.
    """

    # 4. 검증된 모델 설정 (429 에러가 났던 gemini-2.0-flash 사용)
    # URL 기호 오류 방지를 위해 params 사용
    base_url = "[https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent](https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent)"
    params = {'key': api_key}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    raw_text = None
    print(f"🚀 {today_str} 뉴스레터 생성 시작 (24시간 이내 소식 20건)...")

    # 5. 재시도 로직 (무료 플랜 429 에러 대비)
    for i in range(3):
        try:
            response = requests.post(base_url, params=params, json=payload, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print("✅ API 호출 성공!")
                break
            elif response.status_code == 429:
                # 429 에러 시 대기 시간을 더 길게 (무료 플랜은 1분 이상 쉬어야 할 때가 많음)
                wait_sec = 60 * (i + 1)
                print(f"⏳ 할당량 초과(429). {wait_sec}초 후 다시 시도합니다... ({i+1}/3)")
                time.sleep(wait_sec)
            else:
                print(f"⚠️ 에러 발생 ({response.status_code}): {response.text}")
                break
        except Exception as e:
            print(f"⚠️ 연결 에러: {e}")
            break

    if not raw_text:
        print("❌ 뉴스레터 생성에 실패했습니다. 5분 정도 뒤에 다시 시도해 보세요.")
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
        print(f"✅ 뉴스레터 발송 완료! ({target_email})")
    except Exception as e:
        print(f"⚠️ 이메일 발송 실패: {e}")

if __name__ == "__main__":
    send_newsletter()
