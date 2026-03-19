#!/usr/bin/env python3
"""
플랫폼 기획자 데일리 브리프 자동 발송
Naver News API → Gemini 2.5 Flash → Gmail
"""

import os
import re
import json
import smtplib
import urllib.request
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
from datetime import datetime, timezone, timedelta

# ──────────────────────────────────────────────
# 환경변수
# ──────────────────────────────────────────────
NAVER_CLIENT_ID     = os.environ["NAVER_CLIENT_ID"]
NAVER_CLIENT_SECRET = os.environ["NAVER_CLIENT_SECRET"]
GEMINI_API_KEY      = os.environ["GEMINI_API_KEY"]
SMTP_EMAIL          = os.environ["SMTP_EMAIL"]
SMTP_PASSWORD       = os.environ["SMTP_PASSWORD"]
TO_EMAIL            = os.environ.get("TO_EMAIL", SMTP_EMAIL)

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y년 %m월 %d일")
TODAY_WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"][datetime.now(KST).weekday()]

# ──────────────────────────────────────────────
# 카테고리 정의
# ──────────────────────────────────────────────
CATEGORIES = [
    {
        "id": "domestic_game",
        "label": "🎮 국내 게임 시장",
        "color": "#c84b31",
        "queries": ["국내 게임 시장", "한국 게임 신작", "국내 게임사 동향", "넥슨 넷마블 크래프톤"],
    },
    {
        "id": "global_game",
        "label": "🌐 글로벌 게임 시장",
        "color": "#2563b0",
        "queries": ["글로벌 게임 시장", "해외 게임 출시", "닌텐도 소니 마이크로소프트 게임", "스팀 게임 신작"],
    },
    {
        "id": "it",
        "label": "💻 IT 업계",
        "color": "#7c3aed",
        "queries": ["글로벌 빅테크 동향", "구글 애플 마이크로소프트 메타 아마존", "실리콘밸리 테크 뉴스", "글로벌 플랫폼 IT 전략"],
    },
    {
        "id": "ai",
        "label": "🤖 AI",
        "color": "#0891b2",
        "queries": ["글로벌 AI 최신 동향", "오픈AI 앤트로픽 구글 AI", "생성형 AI 글로벌 트렌드", "AI 모델 기술 발표"],
    },
]

# ──────────────────────────────────────────────
# 1단계: 네이버 뉴스 API 수집
# ──────────────────────────────────────────────
def fetch_naver_news(query: str, display: int = 15) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display={display}&sort=date"
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("items", [])
    except Exception as e:
        print(f"[WARN] Naver API error for '{query}': {e}")
        return []

def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).replace("&quot;", '"').replace("&amp;", "&").replace("&#39;", "'").strip()

def normalize_title(title: str) -> str:
    """제목에서 특수문자/공백 제거 후 비교용 문자열 반환"""
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", title).lower()

def collect_articles_for_category(cat: dict, target: int = 5) -> list[dict]:
    """
    카테고리별 기사 target개 수집
    - URL 중복 제거
    - 제목 정규화 후 중복 제거 (같은 기사 다른 URL 방지)
    """
    seen_links = set()
    seen_titles = set()
    articles = []

    for query in cat["queries"]:
        if len(articles) >= target:
            break
        items = fetch_naver_news(query, display=15)
        for item in items:
            if len(articles) >= target:
                break

            link = item.get("originallink") or item.get("link", "")
            title = clean_html(item.get("title", ""))
            norm_title = normalize_title(title)

            # URL 중복 or 제목 유사 중복 제거
            if not link or link in seen_links:
                continue
            if norm_title and norm_title in seen_titles:
                continue
            # 제목 앞 20자 기준으로도 중복 체크
            title_prefix = norm_title[:20]
            if any(title_prefix and s.startswith(title_prefix) for s in seen_titles):
                continue

            seen_links.add(link)
            seen_titles.add(norm_title)
            articles.append({
                "title": title,
                "link": link,
                "description": clean_html(item.get("description", "")),
                "pubDate": item.get("pubDate", ""),
            })

    return articles[:target]

# ──────────────────────────────────────────────
# 2단계: Gemini로 요약/인사이트 생성
# ──────────────────────────────────────────────
def call_gemini(prompt: str, retries: int = 4) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192},
    }).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            wait = 30 * (2 ** attempt)  # 30s, 60s, 120s, 240s
            print(f"    [WARN] Gemini 오류 (시도 {attempt+1}/{retries}): {e} → {wait}초 후 재시도")
            if attempt < retries - 1:
                time.sleep(wait)
            else:
                raise

def analyze_all_categories(all_data: list[dict]) -> list[dict]:
    """
    4개 카테고리를 단일 Gemini 호출로 처리 → API 호출 4번 → 1번으로 감소
    """
    sections = []
    for entry in all_data:
        cat = entry["cat"]
        articles = entry["articles"]
        global_note = ""
        if cat["id"] in ("it", "ai"):
            global_note = " (글로벌 관점 중심, 특정 국가 한정 금지)"
        art_text = "\n".join([
            f"  {i+1}. 제목: {a['title']} | URL: {a['link']} | 설명: {a['description']}"
            for i, a in enumerate(articles)
        ])
        sections.append(f"[카테고리: {cat['label']}{global_note}]\n{art_text}")

    combined = "\n\n".join(sections)

    prompt = f"""당신은 게임/IT 플랫폼 기획자를 위한 뉴스 큐레이터입니다.
아래 4개 카테고리의 뉴스 기사를 분석하세요.

{combined}

다음 JSON 배열 형식으로만 응답하세요. URL은 절대 새로 생성하지 말고 입력된 URL 그대로 사용하세요.

[
  {{
    "category_id": "카테고리 id (domestic_game / global_game / it / ai)",
    "category_insight": "카테고리 전체 핵심 인사이트 2문장 이내",
    "articles": [
      {{
        "title": "원본 기사 제목 그대로",
        "link": "입력된 URL 그대로 (절대 변경 금지)",
        "summary": "기사 핵심 내용 1문장",
        "keywords": ["키워드1", "키워드2", "키워드3"],
        "reason": "플랫폼 기획자가 주목해야 할 이유 1문장"
      }}
    ]
  }}
]

4개 카테고리 모두 포함, 각 카테고리 기사 수 유지, JSON 외 다른 텍스트 출력 금지."""

    raw = call_gemini(prompt)
    raw = raw.strip()
    # 코드블록 제거
    if "```" in raw:
        raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    # JSON 배열 부분만 추출 (앞뒤 잡음 제거)
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start:end+1]
    results_list = json.loads(raw)

    # category_id → dict 로 인덱싱
    result_map = {r["category_id"]: r for r in results_list}

    # URL·제목 원본 강제 보존
    for entry in all_data:
        cat_id = entry["cat"]["id"]
        articles = entry["articles"]
        if cat_id in result_map:
            for i, art in enumerate(result_map[cat_id].get("articles", [])):
                if i < len(articles):
                    art["link"] = articles[i]["link"]
                    art["title"] = articles[i]["title"]

    return result_map

# ──────────────────────────────────────────────
# HTML 생성
# ──────────────────────────────────────────────
def build_html(category_results: list[dict]) -> str:

    BASE_FONT = "'Noto Sans KR', Arial, sans-serif"

    def chip(keyword: str, color: str) -> str:
        return (
            f'<span style="display:inline-block;background:{color}15;color:{color};'
            f'border:1px solid {color}50;border-radius:4px;padding:3px 9px;'
            f'font-size:12px;font-family:{BASE_FONT};font-weight:600;'
            f'margin:2px 4px 2px 0;line-height:1.4;">'
            f'{keyword}</span>'
        )

    def label(text: str) -> str:
        return (
            f'<span style="font-size:10px;font-weight:700;font-family:{BASE_FONT};'
            f'color:#3d3d3a;text-transform:uppercase;letter-spacing:0.4px;">{text}</span>'
        )

    cards_html = ""
    for cr in category_results:
        cat = cr["cat"]
        analyzed = cr["analyzed"]
        color = cat["color"]

        article_items = ""
        for art in analyzed.get("articles", []):
            kw_chips = "".join(chip(kw, color) for kw in art.get("keywords", []))
            article_items += f"""
            <div style="border:1px solid #e8e6e0;border-radius:10px;background:#ffffff;
                        padding:16px 18px;margin-bottom:10px;">
              <div style="font-size:15px;font-weight:600;color:#1a1a18;line-height:1.5;
                          margin-bottom:10px;font-family:{BASE_FONT};">{art['title']}</div>
              <div style="margin-bottom:10px;line-height:1.8;">{kw_chips}</div>
              <table style="width:100%;border-collapse:collapse;">
                <tr style="vertical-align:top;">
                  <td style="width:52px;padding:3px 0;">{label('내용')}</td>
                  <td style="padding:3px 0;font-size:13px;color:#4a4a47;font-family:{BASE_FONT};line-height:1.6;">{art.get('summary','')}</td>
                </tr>
                <tr style="vertical-align:top;">
                  <td style="width:52px;padding:3px 0;">{label('주목')}</td>
                  <td style="padding:3px 0;font-size:13px;color:#4a4a47;font-family:{BASE_FONT};line-height:1.6;">{art.get('reason','')}</td>
                </tr>
                <tr style="vertical-align:top;">
                  <td style="width:52px;padding:3px 0;">{label('링크')}</td>
                  <td style="padding:3px 0;">
                    <a href="{art['link']}" style="font-size:13px;color:{color};
                       text-decoration:none;font-family:{BASE_FONT};line-height:1.6;
                       word-break:break-all;">{art['title']}</a>
                  </td>
                </tr>
              </table>
            </div>"""

        insight_box = ""
        if analyzed.get("category_insight"):
            insight_box = f"""
            <div style="background:{color}0d;border-left:3px solid {color};border-radius:0 8px 8px 0;
                        padding:12px 16px;margin-bottom:12px;">
              <div style="font-size:10px;font-weight:700;color:{color};font-family:{BASE_FONT};
                          letter-spacing:0.4px;margin-bottom:5px;">오늘의 인사이트</div>
              <div style="font-size:13px;color:#2a2a27;line-height:1.7;font-family:{BASE_FONT};">{analyzed['category_insight']}</div>
            </div>"""

        cards_html += f"""
        <div style="margin-bottom:32px;">
          <div style="display:flex;align-items:center;margin-bottom:12px;">
            <div style="width:4px;height:22px;background:{color};border-radius:2px;margin-right:10px;flex-shrink:0;"></div>
            <span style="font-size:16px;font-weight:700;color:{color};font-family:{BASE_FONT};">{cat['label']}</span>
          </div>
          {insight_box}
          {article_items}
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<title>플랫폼 기획자 데일리 브리프 {TODAY}</title>
</head>
<body style="margin:0;padding:0;background:#fafaf8;font-family:'Noto Sans KR',Arial,sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px 40px;">

  <!-- 헤더 -->
  <div style="background:#ffffff;border:1px solid #e8e6e0;border-radius:10px;
              padding:24px 28px;margin-bottom:24px;">
    <div style="font-size:11px;font-weight:600;color:#888884;font-family:'Noto Sans KR',Arial,sans-serif;
                letter-spacing:1px;margin-bottom:6px;">PLATFORM PLANNER DAILY BRIEF</div>
    <div style="font-size:22px;font-weight:700;color:#1a1a18;font-family:'Noto Sans KR',Arial,sans-serif;margin-bottom:4px;">
      {TODAY} ({TODAY_WEEKDAY}) 데일리 브리프
    </div>
    <div style="font-size:13px;color:#888884;font-family:'Noto Sans KR',Arial,sans-serif;">
      국내게임 · 글로벌게임 · IT업계 · AI &mdash; 각 카테고리 5개 기사 · 총 20개
    </div>
  </div>

  <!-- 카테고리 카드들 -->
  {cards_html}

</div>
</body>
</html>"""

# ──────────────────────────────────────────────
# 3단계: Gmail 발송
# ──────────────────────────────────────────────
def send_email(html_content: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[데일리브리프] {TODAY} ({TODAY_WEEKDAY}) 플랫폼 기획자 뉴스"
    msg["From"] = SMTP_EMAIL
    msg["To"] = TO_EMAIL
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, TO_EMAIL.split(","), msg.as_string())
    print(f"[OK] 이메일 발송 완료 → {TO_EMAIL}")

# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    print(f"[{TODAY}] 데일리 브리프 생성 시작")

    # 1단계: 전체 카테고리 기사 수집
    all_data = []
    for cat in CATEGORIES:
        print(f"  ▶ {cat['label']} 기사 수집 중...")
        articles = collect_articles_for_category(cat, target=5)
        print(f"    수집 완료: {len(articles)}개")
        all_data.append({"cat": cat, "articles": articles})

    # 2단계: Gemini 단일 호출로 전체 분석 (API 호출 1회)
    print("  ▶ Gemini 전체 분석 중 (단일 호출)...")
    result_map = analyze_all_categories(all_data)
    print("    분석 완료")

    # 3단계: build_html용 category_results 조립
    category_results = []
    for entry in all_data:
        cat_id = entry["cat"]["id"]
        analyzed = result_map.get(cat_id, {"category_insight": "", "articles": entry["articles"]})
        category_results.append({"cat": entry["cat"], "analyzed": analyzed})

    print("  ▶ HTML 생성 중...")
    html = build_html(category_results)

    with open("newsletter/brief_preview.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("  ▶ brief_preview.html 저장 완료")

    print("  ▶ 이메일 발송 중...")
    send_email(html)
    print("[완료] 데일리 브리프 발송 성공!")

if __name__ == "__main__":
    main()
