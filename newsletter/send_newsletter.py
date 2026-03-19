#!/usr/bin/env python3
"""
플랫폼 기획자 데일리 브리프 자동 발송
Naver News API → Gemini 2.5 Flash → Gmail
"""

import os
import json
import smtplib
import urllib.request
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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
        "queries": ["국내 게임 시장", "한국 게임 신작", "국내 게임사"],
    },
    {
        "id": "global_game",
        "label": "🌐 글로벌 게임 시장",
        "color": "#2563b0",
        "queries": ["글로벌 게임 시장", "해외 게임 출시", "게임 글로벌"],
    },
    {
        "id": "it",
        "label": "💻 IT 업계",
        "color": "#7c3aed",
        "queries": ["IT 업계 동향", "빅테크 뉴스", "플랫폼 IT"],
    },
    {
        "id": "ai",
        "label": "🤖 AI",
        "color": "#0891b2",
        "queries": ["AI 인공지능 최신", "생성형 AI 뉴스", "AI 서비스 출시"],
    },
]

# ──────────────────────────────────────────────
# 1단계: 네이버 뉴스 API 수집
# ──────────────────────────────────────────────
def fetch_naver_news(query: str, display: int = 10) -> list[dict]:
    """네이버 뉴스 API 호출 → [{title, originallink, link, description, pubDate}]"""
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
    """네이버 API 결과의 HTML 태그 제거"""
    import re
    return re.sub(r"<[^>]+>", "", text).replace("&quot;", '"').replace("&amp;", "&").replace("&#39;", "'")

def collect_articles_for_category(cat: dict, target: int = 5) -> list[dict]:
    """카테고리별 기사 target개 수집 (중복 URL 제거)"""
    seen_links = set()
    articles = []
    for query in cat["queries"]:
        if len(articles) >= target:
            break
        items = fetch_naver_news(query, display=10)
        for item in items:
            link = item.get("originallink") or item.get("link", "")
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            articles.append({
                "title": clean_html(item.get("title", "")),
                "link": link,
                "description": clean_html(item.get("description", "")),
                "pubDate": item.get("pubDate", ""),
            })
            if len(articles) >= target:
                break
    return articles[:target]

# ──────────────────────────────────────────────
# 2단계: Gemini로 요약/인사이트 생성
# ──────────────────────────────────────────────
def call_gemini(prompt: str) -> str:
    """Gemini 2.5 Flash API 호출"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-04-17:generateContent?key={GEMINI_API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["candidates"][0]["content"]["parts"][0]["text"]

def analyze_category(cat: dict, articles: list[dict]) -> dict:
    """
    Gemini에 기사 목록 전달 → 각 기사별 요약/키워드/주목사유 + 카테고리 인사이트 반환
    URL은 절대 생성하지 말고 입력된 데이터만 사용하도록 프롬프트에 명시
    """
    articles_text = "\n\n".join([
        f"[기사 {i+1}]\n제목: {a['title']}\nURL: {a['link']}\n설명: {a['description']}"
        for i, a in enumerate(articles)
    ])

    prompt = f"""당신은 게임/IT 플랫폼 기획자를 위한 뉴스 큐레이터입니다.
아래는 '{cat['label']}' 카테고리의 오늘 뉴스 기사 목록입니다.

{articles_text}

다음 JSON 형식으로만 응답하세요. URL은 절대 새로 만들지 말고 입력된 URL을 그대로 사용하세요.

{{
  "category_insight": "카테고리 전체를 아우르는 오늘의 핵심 인사이트 2-3문장",
  "articles": [
    {{
      "title": "원본 기사 제목 그대로",
      "link": "입력된 URL 그대로 (변경 금지)",
      "summary": "기사 핵심 내용 1-2문장 요약",
      "keywords": ["키워드1", "키워드2", "키워드3"],
      "reason": "플랫폼 기획자가 주목해야 할 이유 1문장"
    }}
  ]
}}

반드시 {len(articles)}개 기사 모두 포함하고, JSON 외 다른 텍스트는 출력하지 마세요."""

    raw = call_gemini(prompt)
    # JSON 파싱
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())
    # URL 보존: Gemini가 URL을 바꿨을 경우 원본으로 복원
    for i, art in enumerate(result.get("articles", [])):
        if i < len(articles):
            art["link"] = articles[i]["link"]
            art["title"] = articles[i]["title"]  # 원본 제목도 보존
    return result

# ──────────────────────────────────────────────
# HTML 생성
# ──────────────────────────────────────────────
def build_html(category_results: list[dict]) -> str:
    """최종 HTML 이메일 생성"""

    def chip(keyword: str, color: str) -> str:
        return (
            f'<span style="display:inline-block;background:{color}18;color:{color};'
            f'border:1px solid {color}40;border-radius:4px;padding:2px 8px;'
            f'font-size:11px;font-family:monospace;font-weight:600;margin:2px 3px 2px 0;">'
            f'{keyword}</span>'
        )

    def label(text: str) -> str:
        return (
            f'<span style="font-size:10px;font-weight:700;font-family:monospace;'
            f'color:#3d3d3a;text-transform:uppercase;letter-spacing:0.5px;">{text}</span>'
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
                        padding:16px 18px;margin-bottom:12px;">
              <div style="font-size:15px;font-weight:600;color:#1a1a18;line-height:1.45;
                          margin-bottom:8px;">{art['title']}</div>
              <div style="margin-bottom:8px;">{kw_chips}</div>
              <div style="margin-bottom:6px;">
                {label('내용')}
                <span style="font-size:13px;color:#4a4a47;margin-left:6px;">{art.get('summary','')}</span>
              </div>
              <div style="margin-bottom:6px;">
                {label('주목사유')}
                <span style="font-size:13px;color:#4a4a47;margin-left:6px;">{art.get('reason','')}</span>
              </div>
              <div>
                {label('링크')}
                <a href="{art['link']}" style="font-size:13px;color:{color};margin-left:6px;
                   text-decoration:none;word-break:break-all;">{art['title']}</a>
              </div>
            </div>"""

        insight_box = ""
        if analyzed.get("category_insight"):
            insight_box = f"""
            <div style="background:{color}0d;border-left:3px solid {color};border-radius:0 8px 8px 0;
                        padding:12px 16px;margin-bottom:14px;">
              <div style="margin-bottom:4px;">{label('오늘의 인사이트')}</div>
              <div style="font-size:13px;color:#2a2a27;line-height:1.6;">{analyzed['category_insight']}</div>
            </div>"""

        cards_html += f"""
        <div style="margin-bottom:28px;">
          <div style="display:flex;align-items:center;margin-bottom:12px;">
            <div style="width:4px;height:22px;background:{color};border-radius:2px;margin-right:10px;"></div>
            <span style="font-size:16px;font-weight:700;color:{color};">{cat['label']}</span>
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
<body style="margin:0;padding:0;background:#fafaf8;font-family:'Noto Sans KR',sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px 40px;">

  <!-- 헤더 -->
  <div style="background:#ffffff;border:1px solid #e8e6e0;border-radius:10px;
              padding:24px 28px;margin-bottom:24px;">
    <div style="font-size:11px;font-family:monospace;font-weight:600;color:#888884;
                letter-spacing:1px;margin-bottom:6px;">PLATFORM PLANNER DAILY BRIEF</div>
    <div style="font-size:22px;font-weight:700;color:#1a1a18;margin-bottom:4px;">
      {TODAY} ({TODAY_WEEKDAY}) 데일리 브리프
    </div>
    <div style="font-size:13px;color:#888884;">
      국내게임 · 글로벌게임 · IT업계 · AI — 각 카테고리 5개 기사 · 총 20개
    </div>
  </div>

  <!-- 카테고리 카드들 -->
  {cards_html}

  <!-- 푸터 -->
  <div style="text-align:center;padding-top:16px;border-top:1px solid #e8e6e0;">
    <div style="font-size:11px;font-family:monospace;color:#aaa9a5;">
      자동 생성 · Naver News API + Gemini 2.5 Flash · {TODAY} KST
    </div>
  </div>

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
    category_results = []

    for cat in CATEGORIES:
        print(f"  ▶ {cat['label']} 기사 수집 중...")
        articles = collect_articles_for_category(cat, target=5)
        print(f"    수집 완료: {len(articles)}개")

        print(f"  ▶ {cat['label']} Gemini 분석 중...")
        analyzed = analyze_category(cat, articles)
        category_results.append({"cat": cat, "analyzed": analyzed})
        print(f"    분석 완료")

    print("  ▶ HTML 생성 중...")
    html = build_html(category_results)

    # 로컬 디버그용 저장
    with open("brief_preview.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("  ▶ brief_preview.html 저장 완료")

    print("  ▶ 이메일 발송 중...")
    send_email(html)
    print("[완료] 데일리 브리프 발송 성공!")

if __name__ == "__main__":
    main()
