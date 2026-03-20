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
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
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
TODAY_WEEKDAY = ["월","화","수","목","금","토","일"][datetime.now(KST).weekday()]

# ──────────────────────────────────────────────
# 카테고리 정의
# ──────────────────────────────────────────────

# Gemini 필터링 기준 — 카테고리별 포함/제외 원칙
CATEGORY_RULES = {
    "domestic_game": {
        "include": "넥슨·넷마블·크래프톤·펄어비스·엔씨소프트·카카오게임즈·위메이드 등 국내 게임사의 신작·업데이트·매출·유저반응",
        "exclude": "닌텐도·소니·EA·유비소프트 등 해외 게임사 단독 기사, 주식·증권·시황, AI 기술 자체",
    },
    "global_game": {
        "include": "닌텐도·소니·MS·EA·유비소프트·에픽게임즈·스팀 등 해외 게임사의 신작·서비스·M&A, 글로벌 게임 트렌드",
        "exclude": "넥슨·넷마블·크래프톤·펄어비스 등 국내 게임사 단독 기사, 주식·증권·시황, AI 기술 자체",
    },
    "it": {
        "include": "구글·애플·MS·메타·아마존 등 글로벌 빅테크의 신제품·서비스·정책·플랫폼·클라우드·OS 관련 기사",
        "exclude": "게임 단독 기사, AI 모델·LLM 기술 기사(AI 카테고리 담당), 주식·증권·시황, 박람회 단순 참가 소식",
    },
    "ai": {
        "include": "오픈AI·구글·앤트로픽·MS·메타 등 빅테크의 AI 모델·서비스 출시, LLM 성능·업데이트, AI 비즈니스 전략·규제",
        "exclude": "게임 단독 기사, 의료·보안·로봇 등 단순 AI 적용 사례, 박람회 단순 참가 소식, 주식·증권·시황",
    },
}

# 수집 쿼리 설계 원칙:
# - 회사명 단독 X → "회사명 + 행동/제품/서비스" 조합으로 관련 기사 정밀 수집
# - 글로벌: 한글명+영문명 병행 (네이버에서 해외 기사 잡으려면 영문 필수)
# - IT: 제품/서비스 중심, 주가·시세 등 증권 키워드 배제
# - AI: 모델명·서비스명 직접 지정, "AI+산업명" 조합 제외 (노이즈 유발)
NAVER_QUERIES = {
    "domestic_game": [
        "넥슨 신작 출시 업데이트",
        "넷마블 크래프톤 게임 서비스",
        "펄어비스 엔씨소프트 신작",
        "카카오게임즈 위메이드 컴투스 게임",
        "국내 모바일게임 흥행 순위",
        "한국 PC게임 온라인게임 업데이트",
        "국산 게임 글로벌 서비스",
    ],
    "global_game": [
        "닌텐도 스위치 Nintendo 발표",
        "PS5 플레이스테이션 소니 신작",
        "Xbox 엑스박스 게임패스 출시",
        "스팀 Steam 신작 인기게임",
        "유비소프트 EA 블리자드 신작",
        "해외 콘솔게임 AAA 리뷰 출시",
        "글로벌 게임시장 e스포츠 동향",
    ],
    "it": [
        "애플 아이폰 맥북 iOS 발표",
        "구글 안드로이드 픽셀 서비스",
        "마이크로소프트 윈도우 서피스 발표",
        "메타 인스타그램 페이스북 정책",
        "아마존 AWS 클라우드 발표",
        "앱스토어 구글플레이 수수료 정책",
        "빅테크 반독점 개인정보 규제",
    ],
    "ai": [
        "챗GPT GPT-4o 오픈AI 업데이트",
        "제미나이 Gemini 구글 AI 발표",
        "클로드 Claude 앤트로픽 모델",
        "라마 Llama 메타 AI 출시",
        "코파일럿 Copilot 마이크로소프트 AI",
        "생성형AI LLM 신모델 출시 성능",
        "AI 빅테크 전략 투자 규제",
    ],
}

# 글로벌 게임 전용 RSS (영문 매체 직접 구독 → Gemini가 한국어로 번역)
GLOBAL_GAME_RSS = [
    "https://feeds.feedburner.com/ign/games-all",
    "https://www.gamespot.com/feeds/mashup/",
    "https://www.eurogamer.net/?format=rss",
    "https://www.pcgamer.com/rss/",
    "https://www.videogameschronicle.com/feed/",
]

CATEGORIES = [
    {"id": "domestic_game", "label": "🎮 국내 게임 시장", "color": "#c84b31"},
    {"id": "global_game",   "label": "🌐 글로벌 게임 시장", "color": "#2563b0"},
    {"id": "it",            "label": "💻 IT 업계",          "color": "#7c3aed"},
    {"id": "ai",            "label": "🤖 AI",               "color": "#0891b2"},
]

# ──────────────────────────────────────────────
# 1단계: 기사 수집
# ──────────────────────────────────────────────

def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").replace("&quot;",'"').replace("&amp;","&").replace("&#39;","'").strip()

def normalize_title(title: str) -> str:
    return re.sub(r"[^a-zA-Z0-9가-힣]", "", title).lower()

def is_within_hours(pub: str, hours: int = 24) -> bool:
    try:
        dt = parsedate_to_datetime(pub)
        return (datetime.now(timezone.utc) - dt).total_seconds() <= hours * 3600
    except Exception:
        return True  # 파싱 실패 시 통과

def fetch_naver_news(query: str, display: int = 20) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display={display}&sort=date"
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("items", [])
    except Exception as e:
        print(f"    [WARN] Naver API 오류 '{query}': {e}")
        return []

def fetch_rss(url: str, max_items: int = 20) -> list[dict]:
    """RSS 피드 파싱 → [{title, link, description}]"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            root = ET.fromstring(resp.read())
        items = []
        # RSS 2.0
        for item in root.findall(".//item")[:max_items]:
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link") or "").strip()
            desc  = clean_html(item.findtext("description") or "")[:120]
            if title and link:
                items.append({"title": title, "link": link, "description": desc, "pubDate": ""})
        # Atom fallback
        if not items:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//a:entry", ns)[:max_items]:
                title = (entry.findtext("a:title", namespaces=ns) or "").strip()
                link_el = entry.find("a:link", ns)
                link = (link_el.get("href", "") if link_el is not None else "").strip()
                desc = clean_html(entry.findtext("a:summary", namespaces=ns) or "")[:120]
                if title and link:
                    items.append({"title": title, "link": link, "description": desc, "pubDate": ""})
        return items
    except Exception as e:
        print(f"    [WARN] RSS 오류 {url[:50]}: {e}")
        return []

def collect_articles_for_category(cat: dict, target: int = 10) -> list[dict]:
    """
    카테고리별 독립 수집
    - 기본 48시간 필터 (24h→48h로 완화하여 5개 미달 방지)
    - 글로벌 게임: RSS(영문 매체) + 네이버 API 병행
    - 나머지: 네이버 API
    """
    seen_links = set()
    seen_norms = set()
    articles   = []
    cat_id     = cat["id"]

    def add_article(title, link, desc, pub=""):
        norm = normalize_title(title)
        if not link or link in seen_links or norm in seen_norms:
            return False
        seen_links.add(link)
        seen_norms.add(norm)
        articles.append({"title": title, "link": link, "description": desc, "pubDate": pub})
        return True

    # 글로벌 게임: RSS 먼저 수집 (영문 매체 직접 구독)
    if cat_id == "global_game":
        for feed_url in GLOBAL_GAME_RSS:
            if len(articles) >= target:
                break
            for item in fetch_rss(feed_url):
                if len(articles) >= target:
                    break
                add_article(item["title"], item["link"], item["description"])
        print(f"    RSS 수집: {len(articles)}개")

    # 네이버 API (글로벌 게임은 RSS 보충용, 나머지는 주 수집원)
    # 기본 48시간 필터 적용
    for query in NAVER_QUERIES.get(cat_id, []):
        if len(articles) >= target:
            break
        for item in fetch_naver_news(query):
            if len(articles) >= target:
                break
            if not is_within_hours(item.get("pubDate", ""), 48):
                continue
            link  = item.get("originallink") or item.get("link", "")
            title = clean_html(item.get("title", ""))
            desc  = clean_html(item.get("description", ""))[:120]
            pub   = item.get("pubDate", "")
            add_article(title, link, desc, pub)

    print(f"    수집 완료: {len(articles)}개")
    return articles[:target]

# ──────────────────────────────────────────────
# 2단계: Gemini 분석
# ──────────────────────────────────────────────

def call_gemini(prompt: str, retries: int = 4) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 16384},
    }).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            wait = 30 * (2 ** attempt)
            print(f"    [WARN] Gemini 오류 (시도 {attempt+1}/{retries}): {e} → {wait}초 후 재시도")
            if attempt < retries - 1:
                time.sleep(wait)
            else:
                raise

def build_prompt(batch: list[dict]) -> str:
    """2개 카테고리를 하나의 프롬프트로"""
    sections = []
    rules_text = ""
    for entry in batch:
        cat = entry["cat"]
        cid = cat["id"]
        r   = CATEGORY_RULES[cid]
        rules_text += f"[{cat['label']}] 포함: {r['include']} / 제외: {r['exclude']}\n"
        art_lines = "\n".join(
            f"  {i+1}. {a['title'].replace(chr(34), chr(39))} | {a['link']}"
            for i, a in enumerate(entry["articles"])
        )
        sections.append(f"=== {cat['label']} ===\n{art_lines}")

    combined  = "\n\n".join(sections)
    cat_ids   = " / ".join(e["cat"]["id"] for e in batch)
    cat_labels = " / ".join(e["cat"]["label"] for e in batch)

    # 카테고리별 추가 강조
    extra = ""
    if any(e["cat"]["id"] == "global_game" for e in batch):
        extra += "\n⚠️ 글로벌 게임: 국내 게임사(넥슨·넷마블·크래프톤·펄어비스 등) 기사는 1개도 포함 금지."
    if any(e["cat"]["id"] == "it" for e in batch):
        extra += "\n⚠️ IT 업계: 빅테크 서비스·정책 기사만. 주식·시황·AI 모델 기사 제외. summary/reason 반드시 작성."
    if any(e["cat"]["id"] == "ai" for e in batch):
        extra += "\n⚠️ AI: 빅테크 AI 모델·서비스 기사만. 의료·보안·로봇 박람회 기사 제외. summary/reason 반드시 작성."

    return f"""당신은 게임/IT 플랫폼 기획자를 위한 뉴스 큐레이터입니다.
{extra}

[카테고리별 선정 기준]
{rules_text}
[기사 목록]
{combined}

[지시사항]
1. 각 카테고리에서 선정 기준에 맞는 기사 최대 5개 선정. 기준 벗어난 기사는 제외.
2. 동일 게임·인물·이슈를 다룬 기사가 여러 개면 반드시 1개만 선택. 예: '붉은사막' 관련 기사가 5개여도 1개만 포함.
3. category_insight: 반드시 2문장 이내. 3문장 이상 절대 금지.
4. summary: 기사 핵심 내용 2~3줄. 절대 비우지 말 것.
5. reason: 플랫폼 기획자가 주목해야 할 이유 1~2줄. 절대 비우지 말 것.
6. title: 그대로 사용 (국문 기사는 원본, 영문이면 한국어 번역).
7. link: 입력된 URL만 사용. 절대 새로 생성 금지.

JSON 배열만 출력 (다른 텍스트 없이):
[
  {{
    "category_id": "{cat_ids} 중 정확히 하나",
    "category_insight": "오늘의 핵심 흐름 (반드시 2문장 이내)",
    "articles": [
      {{
        "title": "기사 제목",
        "link": "원본 URL",
        "summary": "핵심 내용 2~3줄 (비우지 말 것)",
        "keywords": ["키워드1", "키워드2", "키워드3"],
        "reason": "기획자 주목 이유 1~2줄 (비우지 말 것)"
      }}
    ]
  }}
]"""

def parse_gemini_json(raw: str) -> list:
    raw = raw.strip()
    if "```" in raw:
        raw = re.sub(r"```(?:json)?", "", raw).replace("```","").strip()
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start:end+1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"    [ERROR] JSON 파싱 실패: {e}")
        print(f"    [DEBUG] 오류 위치: {raw[max(0,e.pos-80):e.pos+80]}")
        raise

def analyze_all_categories(all_data: list[dict]) -> dict:
    """
    2배치 호출: [국내게임+글로벌게임] / [IT+AI]
    - Gemini 2회 호출로 무료 플랜 일일 한도 절약
    - 배치 간 20초 대기
    """
    result_map = {}
    batches = [all_data[:2], all_data[2:]]

    for i, batch in enumerate(batches):
        if i > 0:
            time.sleep(20)
        labels = " + ".join(e["cat"]["label"] for e in batch)
        total  = sum(len(e["articles"]) for e in batch)
        print(f"    [{i+1}/2] {labels} 분석 중 (총 {total}개)...")

        # URL 원본 보존 맵
        url_map = {a["link"]: a["link"] for e in batch for a in e["articles"]}

        raw = call_gemini(build_prompt(batch))
        for r in parse_gemini_json(raw):
            for art in r.get("articles", []):
                if art["link"] in url_map:
                    art["link"] = url_map[art["link"]]
            result_map[r["category_id"]] = r

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
            f'margin:2px 4px 2px 0;line-height:1.4;">{keyword}</span>'
        )

    def label(text: str) -> str:
        return (
            f'<span style="font-size:10px;font-weight:700;font-family:{BASE_FONT};'
            f'color:#3d3d3a;letter-spacing:0.4px;">{text}</span>'
        )

    def link_icon(url: str, color: str) -> str:
        return (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'style="display:inline-block;vertical-align:middle;margin-left:7px;'
            f'font-size:13px;line-height:1;text-decoration:none;color:{color};'
            f'font-family:Arial,sans-serif;flex-shrink:0;">&#x2197;</a>'
        )

    cards_html = ""
    for cr in category_results:
        cat      = cr["cat"]
        analyzed = cr["analyzed"]
        color    = cat["color"]

        article_items = ""
        for art in analyzed.get("articles", []):
            kw_chips = "".join(chip(kw, color) for kw in art.get("keywords", []))
            article_items += f"""
            <div style="border:1px solid #e8e6e0;border-radius:10px;background:#ffffff;
                        padding:16px 18px;margin-bottom:10px;">
              <div style="display:flex;align-items:flex-start;margin-bottom:10px;">
                <span style="font-size:15px;font-weight:600;color:#1a1a18;line-height:1.5;
                             font-family:{BASE_FONT};">{art['title']}</span>{link_icon(art['link'], color)}
              </div>
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
<title>Daily Brief {TODAY}</title>
</head>
<body style="margin:0;padding:0;background:#fafaf8;font-family:'Noto Sans KR',Arial,sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px 40px;">
  <div style="background:#ffffff;border:1px solid #e8e6e0;border-radius:10px;
              padding:24px 28px;margin-bottom:24px;">
    <div style="font-size:22px;font-weight:700;color:#1a1a18;font-family:'Noto Sans KR',Arial,sans-serif;">
      📬 {TODAY} Daily Brief
    </div>
  </div>
  {cards_html}
</div>
</body>
</html>"""

# ──────────────────────────────────────────────
# 3단계: Gmail 발송
# ──────────────────────────────────────────────

def send_email(html_content: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📬 {TODAY} Daily Brief"
    msg["From"]    = SMTP_EMAIL
    msg["To"]      = TO_EMAIL
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

    # 1단계: 카테고리별 독립 수집 (seen 카테고리 내에서만 공유)
    all_data = []
    for cat in CATEGORIES:
        print(f"  ▶ {cat['label']} 기사 수집 중...")
        articles = collect_articles_for_category(cat, target=10)
        all_data.append({"cat": cat, "articles": articles})

    # 2단계: Gemini 2배치 분석
    print("  ▶ Gemini 분석 중...")
    result_map = analyze_all_categories(all_data)
    print("    분석 완료")

    # 3단계: HTML 생성
    category_results = []
    for entry in all_data:
        cat_id   = entry["cat"]["id"]
        analyzed = result_map.get(cat_id, {"category_insight": "", "articles": entry["articles"][:5]})
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
