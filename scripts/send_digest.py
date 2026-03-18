import os
import requests
import json
import smtplib
import re
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

def get_news_segment(api_key, fields, limit_time):
    """분야를 나눠서 요청하여 할당량 에러 방지"""
    prompt = f"""
    IT/게임 전략 기획자용 뉴스레터를 작성하세요. 기준: {limit_time} 이후 24시간 내 소식.
    대상 분야: {fields} (각 5개씩 총 10개)
    형식: [제목], [1문장 요약], [링크] 포함한 HTML 카드 형태.
    순수 HTML로만 응답하세요.
    """
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    for _ in range(3):
        res = requests.post(url, params={'key': api_key}, 
                            json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=120)
        if res.status_code == 200:
            return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        time.sleep(60) # 실패 시 1분 대기
    return ""

def send_newsletter():
    api_key = os.environ.get("GEMINI_API_KEY")
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    target_email = "seonyoung@ncsoft.com"

    limit_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    print("🚀 1차 뉴스 생성 중 (국내/국외 게임)...")
    part1 = get_news_segment(api_key, "1.국내게임시장, 2.국외게임시장", limit_time)
    
    print("⏳ 서버 부하 방지를 위해 30초 휴식...")
    time.sleep(30)
    
    print("🚀 2차 뉴스 생성 중 (IT시장/AI변화)...")
    part2 = get_news_segment(api_key, "3.IT시장, 4.AI변화", limit_time)

    if part1 and part2:
        full_html = part1 + "<hr>" + part2
        clean_html = re.sub(r'```html|```', '', full_html).strip()
        
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = target_email
        msg['Subject'] = f"[Daily Digest] {datetime.now().strftime('%Y-%m-%d')} IT/게임 동향 (20건)"
        msg.attach(MIMEText(clean_html, 'html'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, target_email, msg.as_string())
        print("✅ 전체 발송 성공!")

if __name__ == "__main__":
    send_newsletter()
