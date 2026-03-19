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

CATEGORY_RULES = {
    "domestic_game": {
        "include": "국내(한국) 게임사 신작·업데이트·매출·유저 반응·정책·규제",
        "exclude": "해외 게임사 단독, 반도체·GPU, AI 기술 자체, 글로벌 콘솔 하드웨어, 주식·투자",
    },
    "global_game": {
        "include": "해외 게임사(닌텐도·소니·MS·EA·유비소프트·에픽 등) 신작·서비스·인수합병, 글로벌 게임 트렌드, e스포츠",
        "exclude": "국내 게임사 단독, 반도체·GPU, AI 기술 자체, 주식·투자",
    },
    "it": {
        "include": "글로벌 빅테크(구글·애플·MS·메타·아마존) 신제품·서비스·정책·실적, 클라우드, 반도체, 플랫폼 전략",
        "exclude": "게임 단독, AI 모델·LLM 기술(AI 카테고리), 주식·투자·증권 단독",
    },
    "ai": {
        "include": "LLM·생성형AI 모델 출시·성능, AI 스타트업·빅테크 AI 전략, AI 규제·정책, AI 서비스 글로벌 트렌드",
        "exclude": "게임 단독, 반도체 하드웨어 단독, 주식·투자 단독",
    },
}

# ─────────────────────────────────────────────────────────────────
# 수집 소스 정의 — 전 카테고리 네이버 API 통일
#  네이버 sort=sim(관련도순): 품질·클릭수 반영, 영세매체 낚시성 기사 자연 필터링
# ─────────────────────────────────────────────────────────────────

NAVER_QUERIES = {
    "domestic_game": [
        "국내 모바일게임 신작 출시",
        "넥슨 넷마블 크래프톤 펄어비스 게임",
        "국내 온라인게임 콘솔게임 업데이트",
        "한국 게임업계 매출 서비스",
    ],
    "global_game": [
        "닌텐도 소니 플레이스테이션 신작",
        "Xbox 마이크로소프트 게임 서비스",
        "글로벌 게임사 신작 출시 해외",
        "에픽게임즈 EA 유비소프트 블리자드",
        "스팀 콘솔 게임 글로벌 출시",
    ],
    "it": [
        "구글 애플 마이크로소프트 서비스 발표",
        "메타 아마존 빅테크 플랫폼 전략",
        "반도체 엔비디아 퀄컴 TSMC",
        "애플 안드로이드 모바일 OS 정책",
        "글로벌 IT 업계 인수합병 실적",
    ],
    "ai": [
        "오픈AI GPT 생성형AI 신모델",
        "구글 제미나이 앤트로픽 AI 출시",
        "AI 서비스 글로벌 트렌드 정책",
        "LLM 인공지능 빅테크 전략",
        "AI 규제 산업 적용 사례",
    ],
}

CATEGORIES = [
    {"id": "domestic_game", "label": "🎮 국내 게임 시장", "color": "#c84b31"},
    {"id": "global_game",   "label": "🌐 글로벌 게임 시장", "color": "#2563b0"},
    {"id": "it",            "label": "💻 IT 업계",          "color": "#7c3aed"},
    {"id": "ai",            "label": "🤖 AI",               "color": "#0891b2"},
]

# ──────────────────────────────────────────────
# 1단계: 기사 수집 (국내=네이버API / 글로벌·IT·AI=RSS)
# ──────────────────────────────────────────────
def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").replace("&quot;",'"').replace("&amp;","&").replace("&#39;","'").strip()

def normalize_title(title: str) -> str:
    return re.sub(r"[^a-zA-Z0-9가-힣]", "", title).lower()

def fetch_naver_news(query: str, display: int = 15) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display={display}&sort=sim"
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("items", [])
    except Exception as e:
        print(f"    [WARN] Naver API 오류 '{query}': {e}")
        return []

def fetch_rss(url: str, max_items: int = 15) -> list[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        items = []
        # RSS 2.0
        for item in root.findall(".//item")[:max_items]:
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link") or "").strip()
            desc  = clean_html(item.findtext("description") or "")[:120]
            if title and link:
                items.append({"title": title, "link": link, "description": desc})
        # Atom fallback
        if not items:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//a:entry", ns)[:max_items]:
                title = (entry.findtext("a:title", namespaces=ns) or "").strip()
                link_el = entry.find("a:link", ns)
                link = (link_el.get("href","") if link_el is not None else "").strip()
                desc = clean_html(entry.findtext("a:summary", namespaces=ns) or "")[:120]
                if title and link:
                    items.append({"title": title, "link": link, "description": desc})
        return items
    except Exception as e:
        print(f"    [WARN] RSS 오류 {url[:55]}: {e}")
        return []

def dedup(articles: list[dict], seen_links: set, seen_titles: set) -> list[dict]:
    result = []
    for a in articles:
        link = a["link"]
        norm = normalize_title(a["title"])
        if not link or link in seen_links:
            continue
        if norm and norm in seen_titles:
            continue
        if norm[:20] and any(s.startswith(norm[:20]) for s in seen_titles):
            continue
        seen_links.add(link)
        seen_titles.add(norm)
        result.append(a)
    return result

def naver_to_article(item: dict) -> dict:
    return {
        "title": clean_html(item.get("title", "")),
        "link":  item.get("originallink") or item.get("link", ""),
        "description": clean_html(item.get("description", ""))[:120],
    }

def collect_articles_for_category(cat: dict, target: int = 10) -> list[dict]:
    """
    국내 게임 / IT / AI : 네이버 API (한국어)
    글로벌 게임          : 국내 매체 RSS (한국어 번역 기사)
    target개 수집 → Gemini가 최적 5개 선별
    """
    seen_links, seen_titles = set(), set()
    articles = []
    cat_id = cat["id"]

    # 전 카테고리 네이버 API
    for query in NAVER_QUERIES.get(cat_id, []):
        if len(articles) >= target:
            break
        raw_items = fetch_naver_news(query, display=15)
        candidates = [naver_to_article(i) for i in raw_items]
        articles += dedup(candidates, seen_links, seen_titles)

    print(f"    수집 완료: {len(articles)}개 (목표 {target}개)")
    return articles[:target]

# ──────────────────────────────────────────────
# 2단계: Gemini로 요약/인사이트 생성
# ──────────────────────────────────────────────
def call_gemini(prompt: str, retries: int = 4) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 16384},
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

def _build_prompt(batch: list[dict]) -> str:
    """배치(2개 카테고리)용 Gemini 프롬프트 생성"""
    rules_text = ""
    sections = []
    for entry in batch:
        cat = entry["cat"]
        articles = entry["articles"]
        cid = cat["id"]
        r = CATEGORY_RULES[cid]
        rules_text += f"- {cat['label']}: 포함={r['include']} / 제외={r['exclude']}\n"
        global_note = " (글로벌 관점 중심)" if cid in ("it", "ai") else ""
        art_text = "\n".join([
            f"  {i+1}. {a['title'].replace(chr(34), chr(39))} | {a['link']}"
            for i, a in enumerate(articles)
        ])
        sections.append(f"[{cat['label']}{global_note}]\n{art_text}")
    combined = "\n\n".join(sections)
    cat_ids = " / ".join(e["cat"]["id"] for e in batch)

    return f"""당신은 게임/IT 플랫폼 기획자를 위한 뉴스 큐레이터입니다.

[선정 기준]
{rules_text}
[기사 목록]
{combined}

[지시사항]
1. 각 카테고리에서 선정 기준에 적합한 기사를 가능한 5개 선정. 부적합 기사는 제외.
   - 동일 게임·주제·이슈를 다룬 기사가 여러 개면 가장 핵심적인 1개만 선택. 절대 중복 금지.
   - 5개가 안 되면 있는 기사만 포함. 억지로 채우지 말 것.
   - 화제성·파급력 높은 기사 우선.
2. title 필드: 영문 제목은 반드시 자연스러운 한국어로 번역. 국문 제목은 그대로.
3. URL은 절대 새로 생성 금지. 반드시 입력된 URL만 사용.

JSON 배열만 출력하세요 (다른 텍스트 금지):
[
  {{
    "category_id": "{cat_ids} 중 하나",
    "category_insight": "핵심 흐름 1~2문장.",
    "articles": [
      {{
        "title": "한국어 제목 (영문이면 번역, 국문이면 원본 그대로)",
        "link": "원본 URL 그대로 (절대 변경 금지)",
        "summary": "3줄 이내 핵심 요약. 숫자·고유명사 포함.",
        "keywords": ["키워드1", "키워드2", "키워드3"],
        "reason": "기획자가 주목할 이유 2줄 이내."
      }}
    ]
  }}
]"""


def _parse_gemini_json(raw: str) -> list:
    """Gemini 응답에서 JSON 배열 파싱 (견고한 버전)"""
    raw = raw.strip()
    if "```" in raw:
        raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start:end+1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"    [ERROR] JSON 파싱 실패: {e}")
        print(f"    [DEBUG] 응답 앞 500자: {raw[:500]}")
        print(f"    [DEBUG] 오류 위치 주변: {raw[max(0,e.pos-50):e.pos+50]}")
        raise


def analyze_all_categories(all_data: list[dict]) -> dict:
    """
    2개 카테고리씩 나눠 2번 호출 → 응답 길이 절반으로 줄여 JSON 잘림 방지
    호출 간 15초 대기로 rate limit 회피
    """
    result_map = {}

    batches = [all_data[:2], all_data[2:]]  # [게임2개] / [IT+AI]
    for i, batch in enumerate(batches):
        if i > 0:
            time.sleep(15)  # 배치 간 대기
        cat_labels = " + ".join(e["cat"]["label"] for e in batch)
        print(f"    배치 {i+1}/2 분석 중: {cat_labels}")
        prompt = _build_prompt(batch)
        raw = call_gemini(prompt)
        results_list = _parse_gemini_json(raw)
        for r in results_list:
            result_map[r["category_id"]] = r

    # URL만 원본으로 보존 (제목은 Gemini 번역본 사용)
    for entry in all_data:
        cat_id = entry["cat"]["id"]
        articles = entry["articles"]
        if cat_id in result_map:
            for i, art in enumerate(result_map[cat_id].get("articles", [])):
                if i < len(articles):
                    art["link"] = articles[i]["link"]  # URL 원본 강제 보존
                    # title은 Gemini 번역본 유지 (영문→한국어)

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

    # 외부 링크 아이콘 — Gmail은 SVG 차단하므로 텍스트 이모지 사용
    def link_icon_html(url: str, color: str) -> str:
        return (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'style="display:inline-block;vertical-align:middle;margin-left:7px;'
            f'font-size:13px;line-height:1;text-decoration:none;color:{color};'
            f'font-family:Arial,sans-serif;flex-shrink:0;">&#x2197;</a>'
        )

    cards_html = ""
    for cr in category_results:
        cat = cr["cat"]
        analyzed = cr["analyzed"]
        color = cat["color"]

        article_items = ""
        for art in analyzed.get("articles", []):
            kw_chips = "".join(chip(kw, color) for kw in art.get("keywords", []))
            link_icon = link_icon_html(art["link"], color)
            article_items += f"""
            <div style="border:1px solid #e8e6e0;border-radius:10px;background:#ffffff;
                        padding:16px 18px;margin-bottom:10px;">
              <div style="display:flex;align-items:flex-start;margin-bottom:10px;">
                <span style="font-size:15px;font-weight:600;color:#1a1a18;line-height:1.5;
                             font-family:{BASE_FONT};">{art['title']}</span>{link_icon}
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
<title>플랫폼 기획자 데일리 브리프 {TODAY}</title>
</head>
<body style="margin:0;padding:0;background:#fafaf8;font-family:'Noto Sans KR',Arial,sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px 40px;">

  <!-- 헤더 -->
  <div style="background:#ffffff;border:1px solid #e8e6e0;border-radius:10px;
              padding:24px 28px;margin-bottom:24px;">
    <div style="font-size:22px;font-weight:700;color:#1a1a18;font-family:'Noto Sans KR',Arial,sans-serif;">
      📬 {TODAY} Platform Planner Daily Brief
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
    msg["Subject"] = f"📬 {TODAY} Platform Planner Daily Brief"
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
        articles = collect_articles_for_category(cat, target=7)  # 필터링 여유분
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
