import os, requests

api_key = os.environ.get("GEMINI_API_KEY", "").strip()
# 구글이 너한테 허락한 모델이 뭔지 직접 물어보는 주소
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

print(f"DEBUG: 사용 중인 키의 앞자리: {api_key[:4]}...")

try:
    response = requests.get(url)
    print("--- 구글이 보내준 모델 리스트 시작 ---")
    print(response.text)
    print("--- 구글이 보내준 모델 리스트 끝 ---")
except Exception as e:
    print(f"접속 시도 중 에러: {e}")
