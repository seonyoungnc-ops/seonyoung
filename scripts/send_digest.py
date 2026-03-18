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
    # 1. 새 환경 변수 로드 (반드시 새 키를 적용해주세요)
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    if not api_key:
        print("❌ 오류: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        return

    # 2. 날짜 설정 (24시간 이내 최신성 확보)
    now = datetime.now()
    today_str = now.strftime("%Y년 %m월 %d일")
    time_limit = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    # 3. [기획자 요구사항] 상세 프롬프트 (20건 큐레이션)
    prompt = f"""
    당신은 IT/게임 전문 전략 기획자입니다. 오늘은 {today_str}입니다.
    반드시 {time_limit} 이후 최근 24시간 내 발생한 뉴스만 엄선하여 아래 4분야별 각 5개씩(총 20개) HTML 뉴스레터를 만드세요.
    1.국내게임시장 2.국외게임시장 3.IT시장 4.AI변화
    - 항목별 구성: [제목], [1~2문장의 전문적인 핵심 요약], [관련 기사 링크]
    - 디자인: 배경 #f4f4f4, 카드 #ffffff, 제목 강조색 #003366 (가독성 높은 리포트 스타일)
    - 반드시 <html> 태그로 시작하는 순수 HTML만 응답하세요. (마크다운 기호 금지)
    """

    # 4. 주소 기호 오류 원천 차단 (리스트 결합 방식)
    # 에디터가 자동으로 하이퍼링크를 입히지 못하도록 주소를 조각내어 합칩니다.
    url_parts = ["h","t","t","p","s",":","/","/","g","e","n","e","r","a","t","i","v","e","l","a","n","g","u","a","g","e",".","g","o","o","g","l","e","a","p","i","s",".","c","o","m","/","v","1","b","e","t","a","/","m","o","d","e","l","s","/","g","e","m","i","n","i","-","2",".","0","-","f","l","a","s","h",":","g","e","n","e","r","a","t","e","C","o","n","t","e","n","t"]
    endpoint = "".join(url_parts)

    print(f"🚀 {today_str} 뉴스레터 생성 시작 (분야별 5건, 총 20건)...")

    # 5. API 실행 (params 방식을 사용하여 URL 오염 방지)
    try:
        # 429 에러 방지를 위해 5초 대기 후 실행
        time.sleep(5)
        response = requests.post(
            endpoint, 
            params={'key': api_key}, 
            json={"contents": [{"parts": [{"text": prompt}]}]}, 
            timeout=120
        )
        
        if response.status_code == 200:
            raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            print("✅ 뉴스레터 본문 생성 성공!")
            
            # 6. 이메일 발송
            clean_html = re.sub(r'```html|```', '', raw_text).strip()
            msg = MIMEMultipart()
            msg['From'] = smtp_email
            msg['To'] = target_email
            msg['Subject'] = f"[Daily Digest] {today_str} IT/게임 산업 동향 리포트 (20건)"
            msg.attach(MIMEText(clean_html, 'html'))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, target_email, msg.as_string())
            print(f"✅ 발송 완료! ({target_email})")
            
        elif response.status_code == 429:
            print("⏳ 할당량 초과(429). 새 API 키가 맞는지 확인하시고 1분 뒤 다시 시도해주세요.")
        else:
            print(f"❌ 실패 ({response.status_code}): {response.text}")
            
    except Exception as e:
        print(f"⚠️ 에러 발생: {e}")

if __name__ == "__main__":
    send_newsletter()
