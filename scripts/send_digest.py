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

    # 1. 사용 가능한 모델 리스트를 먼저 가져옵니다.
    print("🔍 사용 가능한 모델 리스트 확인 중...")
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        models_res = requests.get(list_url)
        if models_res.status_code != 200:
            print(f"❌ 모델 리스트 획득 실패: {models_res.status_code}")
            return

        # 'gemma'가 포함된 모델을 먼저 찾고, 없으면 'gemini-1.5-flash'를 찾습니다.
        model_list = [m['name'] for m in models_res.json().get('models', [])]
        target_model = next((m for m in model_list if 'gemma' in m), None)
        if not target_model:
            target_model = next((m for m in model_list if 'gemini-1.5-flash' in m), "models/gemini-1.5-flash")

        print(f"✅ 선택된 모델: {target_model}")

        # 2. 선택된 모델로 뉴스레터 생성 (인사이트 중심 큐레이션 스타일)
        prompt = f"""
        당신은 NCSOFT 전략 기획팀의 시니어 플래너입니다. {limit_time} 이후의 시장 동향을 아래 형식에 맞춰 보고하세요.

        1. 리포트 범위 (분야별 5개, 총 20개 필수):
           - [국내 게임 시장], [국외 게임 시장], [AI 시장], [IT 시장]

        2. 개별 뉴스 작성 형식 (중요):
           - [제목]: 뉴스 제목을 명확히 작성
           - 내용 1줄 요약: 핵심 내용을 한 문장으로 정리
           - 원문 Link: 클릭 시 해당 기사로 바로 이동하는 유효한 URL (반드시 검증된 링크만 사용)
           - 주목해야 하는 이유: 기획자 관점에서 이 뉴스가 시장에 미칠 영향이나 인사이트 (2~3줄)

        3. 디자인 가이드 (카드 UI):
           - 배경색 #5c00d2 (진한 보라색) 헤더 적용.
           - 각 뉴스는 흰색 배경의 카드 형태로 구분하며, 하단에 옅은 회색 구분선을 넣으세요.
           - 카테고리(분야)는 배경색 #f4f4f4에 보라색 굵은 글씨로 강조하세요.

        4. 출력 규칙:
           - 반드시 <html>로 시작하여 </html>로 끝나는 순수 코드만 출력.
           - 서론, 결론, 마크다운(```), 설명글 절대 금지.
           - URL은 반드시 'https://'로 시작하는 실제 작동하는 링크여야 함.
        """

        # (API 호출 로직 및 후처리 로직은 그대로 유지)
        if res.status_code == 200:
            raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            
            # Gemma의 설명을 잘라내고 HTML만 추출 (이전과 동일)
            html_match = re.search(r'(<html.*</html>)', raw_text, re.DOTALL | re.IGNORECASE)
            clean_html = html_match.group(1) if html_match else re.sub(r'```html|```', '', raw_text).strip()

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, target_email, msg.as_string())
            print("✅ 메일 발송 완료!")
        else:
            print(f"❌ 생성 실패 (에러코드: {res.status_code})")
            print(f"상세내용: {res.text}")

    except Exception as e:
        print(f"⚠️ 시스템 오류: {e}")

if __name__ == "__main__":
    send_newsletter()
