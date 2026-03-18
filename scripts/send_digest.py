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

    # [최종 최적화 프롬프트]
    prompt = f"""
    당신은 IT/게임 기획자입니다. {limit_time} 이후 24시간 내 뉴스를 큐레이션하세요.
   
    1. 대상 분야 (분야별 5개씩 총 20개 뉴스): 
       - 국내게임시장, 국외게임시장, IT시장, AI기술변화
    
    2. 디자인 가이드 (반드시 준수):
       - 전체 테마: 진한 보라색(#5c00d2)을 헤더 배경색과 표의 강조색으로 사용
       - 텍스트 스타일: 본문 폰트 크기 12px, 제목 및 헤더 폰트 크기 14px (고딕체 계열)
       - 레이아웃: 각 분야별로 '표(Table)' 형식을 사용하여 [뉴스 제목], [핵심 요약(1~2문장)], [원문 링크]를 깔끔하게 배치
       - 스타일: 표의 경계선은 연한 회색(#dddddd)으로 하고, 가독성을 위해 셀 여백(padding)을 충분히 부여
    
    3. 출력 형식:
       - 반드시 <html> 태그로 시작하는 '순수 HTML' 코드만 응답하세요. (마크다운 기호 금지)
       - 스타일은 인라인 CSS(<style> 태그 또는 style="")를 사용하여 이메일에서도 깨지지 않게 작성하세요.
    """

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    print("🚀 뉴스레터 생성 시작...")
    try:
        res = requests.post(url, params={'key': api_key}, 
                            json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=120)
        
        if res.status_code == 200:
            raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            print("✅ 본문 생성 성공!")
            
            # 발송 로직
            clean_html = re.sub(r'```html|```', '', raw_text).strip()
            msg = MIMEMultipart()
            msg['From'] = smtp_email
            msg['To'] = target_email
            msg['Subject'] = f"[Daily Digest] {now.strftime('%Y-%m-%d')} IT/게임 동향 (20건)"
            msg.attach(MIMEText(clean_html, 'html'))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, target_email, msg.as_string())
            print("✅ 메일 발송 완료! 보낸 편지함을 확인하세요.")
        else:
            print(f"❌ 생성 실패 (에러코드: {res.status_code})")
            print(f"상세내용: {res.text}")
    except Exception as e:
        print(f"⚠️ 시스템 오류: {e}")

if __name__ == "__main__":
    send_newsletter()
