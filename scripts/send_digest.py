import os
import requests
import json
import smtplib
import re
import time
import base64
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

    # 2. 날짜 설정
    now = datetime.now()
    today_str = now.strftime("%Y년 %m월 %d일")
    time_limit = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    # 3. [기획자 요구사항] 상세 프롬프트 (20건 큐레이션)
    prompt = f"""
    당신은 IT/게임 전문 전략 기획자입니다. 오늘은 {today_str}입니다.
    반드시 {time_limit} 이후 최근 24시간 내 발생한 뉴스만 엄선하여 아래 4분야별 각 5개씩(총 20개) HTML 뉴스레터를 만드세요.
    1.국내게임시장 2.국외게임시장 3.IT시장 4.AI변화
    - 항목: [제목], [1~2문장 핵심 요약], [관련 링크]
    - 디자인: 배경 #f4f4f4, 카드 #ffffff, 제목색 #003366
    - 마크다운(```) 없이 순수 <html> 태그로만 응답하세요.
    """

    # 4. 주소 기호 오류 원천 봉쇄 (Base64 인코딩 주소 사용)
    # 복사 시 발생하는 하이퍼링크 기호가 주소를 오염시키는 것을 물리적으로 막습니다.
    encoded_url = "aHR0cHM6Ly9nZW5lcmF0aXZlbGFuZ3VhZ2UuZ29vZ2xlYXBpcy5jb20vdjFiZXRhL21vZGVscy9nZW1pbmktMi4wLWZsYXNoOmdlbmVyYXRlQ29udGVudA=="
    endpoint = base64.b64decode(encoded_url).decode('utf-8')

    raw_text = None
    print(f"🚀 {today_str} 뉴스레터 생성 시작 (24시간 소식 20건)...")

    # 5. 실행 및 429 에러 대응 (120초 대기)
    for i in range(3):
        try:
            # params를 사용하여 API 키를 분리 전달 (URL 오염 방지)
            response = requests.post(
                endpoint, 
                params={'key': api_key}, 
                json={"contents": [{"parts": [{"text": prompt}]}]}, 
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print("✅ 뉴스레터 본문 생성 성공!")
                break
            elif response.status_code == 429:
                wait_sec = 120 * (i + 1)
                print(f"⏳ 할당량 초과. {wait_sec}초 후 강제 재시도... ({i+1}/3)")
                time.sleep(wait_sec)
            else:
                print(f"❌ API 오류 ({response.status_code})")
                break
        except Exception as e:
            # 에러 발생 시 주소를 수동으로 다시 한 번 선언
            endpoint = "[https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent](https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent)"
            print(f"⚠️ 연결 시도 중... (재시도 {i+1})")
            time.sleep(10)

    if not raw_text:
        print("❌ 실패: 할당량 문제 혹은 네트워크 환경을 확인하세요.")
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
        print(f"✅ 발송 완료! ({target_email})")
    except Exception as e:
        print(f"⚠️ 이메일 발송 실패: {e}")

if __name__ == "__main__":
    send_newsletter()
