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
        "include": "국내 게임사(넥슨·넷마블·크래프톤·펄어비스·엔씨소프트 등) 신작 출시·업데이트·매출·유저 반응·정책",
        "exclude": "해외 게임사 단독 뉴스, 반도체·주식·투자, AI 기술 자체, 붉은사막 등 이미 다른 카테고리에 포함된 주제",
    },
    "global_game": {
        "include": "닌텐도·소니·MS·EA·유비소프트·에픽게임즈 등 해외 게임사 신작·서비스·M&A, 글로벌 콘솔·PC 게임 트렌드",
        "exclude": "국내 게임사(넥슨·넷마블·크래프톤·펄어비스 등) 단독 뉴스, 붉은사막 관련 기사 전부 제외(국내 카테고리 담당), 반도체·주식",
    },
    "it": {
        "include": "구글·애플·MS·메타·아마존 등 글로벌 빅테크의 신제품·서비스 발표·정책·플랫폼 전략·클라우드·OS",
        "exclude": "게임 관련 기사, AI 모델·LLM 자체(AI 카테고리 담당), 국내 반도체 주식·증권 시황, 박람회·전시회 단순 참가 소식",
    },
    "ai": {
        "include": "오픈AI·구글·앤트로픽·MS 등 빅테크의 AI 모델·서비스 출시·업데이트, LLM 성능 비교, AI 비즈니스 전략·투자·규제",
        "exclude": "게임 관련 기사, 의료·보안·로봇·제조 등 단순 AI 적용 사례(빅테크 AI 전략과 무관한 것), 박람회·전시회 단순 참가 소식, 주식·증권",
    },
}

# ─────────────────────────────────────────────────────────────────
# 수집 쿼리 — 카테고리별 핵심 키워드 중심, 노이즈 최소화
# ─────────────────────────────────────────────────────────────────

# 카테고리 간 키워드 중복 방지 원칙:
# - 국내게임: 국내 게임사명만 사용
# - 글로벌게임: 해외 게임사명만 사용, 국내사명 절대 포함 금지
# - IT: 빅테크 서비스/제품 중심, 게임/AI 키워드 배제
# - AI: 모델명/서비스명 중심, IT 인프라/게임 키워드 배제
NAVER_QUERIES = {
    "domestic_game": [
        "넥슨 게임 출시",
        "넷마블 신작",
        "크래프톤 게임",
        "펄어비스 엔씨소프트 게임",
        "카카오게임즈 위메이드 신작",
    ],
    "global_game": [
        "닌텐도 신작",
        "플레이스테이션 PS5 게임",
        "Xbox 게임패스",
        "EA 유비소프트 신작",
        "스팀 글로벌 게임",
    ],
    "it": [
        "애플 신제품 발표",
        "구글 서비스 업데이트",
        "메타 플랫폼 전략",
        "아마존 마이크로소프트 클라우드",
        "빅테크 정책 발표",
    ],
    "ai": [
        "오픈AI 챗GPT 출시",
        "구글 제미나이 업데이트",
        "앤트로픽 클로드 모델",
        "AI 모델 서비스 출시",
        "LLM 생성형AI 발표",
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
    """특수문자·공백 제거 후 소문자화"""
    return re.sub(r"[^a-zA-Z0-9가-힣]", "", title).lower()

def extract_keywords(title: str) -> set[str]:
    """
    제목에서 2자 이상 의미 단어를 추출 — 동일 주제 탐지용
    예: '붉은사막 출시' → {'붉은사막', '출시'}
    """
    norm = normalize_title(title)
    # 한글 2자+ 또는 영문 3자+ 단어 추출
    words = set(re.findall(r"[가-힣]{2,}|[a-zA-Z]{3,}", norm))
    # 너무 일반적인 단어 제거
    stopwords = {"출시","업데이트","신작","게임","뉴스","발표","서비스","기사",
                 "분석","전략","시장","글로벌","국내","해외","관련","공식","최신",
                 "the","and","for","with","that","this"}
    return words - stopwords

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

def dedup(articles: list[dict], seen_links: set, seen_titles: set,
          seen_kw: set | None = None) -> list[dict]:
    """
    4중 중복 필터:
    1. URL 동일
    2. 정규화 제목 동일
    3. 핵심 키워드 2개 이상 겹침 (동일 주제 다른 기사 차단)
    seen_kw: 카테고리 내/간 공유되는 키워드 세트 (호출 간 누적)
    """
    if seen_kw is None:
        seen_kw = set()
    result = []
    for a in articles:
        link = a["link"]
        norm = normalize_title(a["title"])
        kws  = extract_keywords(a["title"])

        if not link or link in seen_links:
            continue
        if norm in seen_titles:
            continue
        # 핵심 키워드 2개 이상 겹치면 동일 주제로 판단 → 제외
        if len(kws & seen_kw) >= 2:
            continue

        seen_links.add(link)
        seen_titles.add(norm)
        seen_kw.update(kws)   # 누적 (참조 전달이므로 외부에서도 반영됨)
        result.append(a)
    return result

def parse_pubdate(pub: str) -> datetime | None:
    """네이버 API pubDate(RFC 2822) → datetime(UTC)"""
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(pub)
    except Exception:
        return None

def is_within_hours(pub: str, hours: int = 24) -> bool:
    """발행일이 현재 기준 hours 시간 이내인지 확인"""
    dt = parse_pubdate(pub)
    if dt is None:
        return True  # 날짜 파싱 실패 시 통과
    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() <= hours * 3600

def naver_to_article(item: dict) -> dict:
    return {
        "title":       clean_html(item.get("title", "")),
        "link":        item.get("originallink") or item.get("link", ""),
        "description": clean_html(item.get("description", ""))[:120],
        "pubDate":     item.get("pubDate", ""),
    }

def collect_articles_for_category(
    cat: dict,
    target: int = 10,
    global_seen_links: set | None = None,
    global_seen_titles: set | None = None,
    global_seen_kw: set | None = None,
) -> list[dict]:
    """
    전 카테고리 네이버 API — 24h 필터 + 4중 중복 제거
    - seen_links / seen_titles / seen_kw 를 카테고리 간 공유 → 교차 중복 차단
    - 부족 시 48h 자동 확장
    """
    seen_links  = global_seen_links  if global_seen_links  is not None else set()
    seen_titles = global_seen_titles if global_seen_titles is not None else set()
    seen_kw     = global_seen_kw     if global_seen_kw     is not None else set()
    articles = []
    cat_id = cat["id"]

    for hours in (24, 48):
        if len(articles) >= target:
            break
        for query in NAVER_QUERIES.get(cat_id, []):
            if len(articles) >= target:
                break
            raw_items = fetch_naver_news(query, display=20)
            candidates = [
                naver_to_article(i) for i in raw_items
                if is_within_hours(i.get("pubDate", ""), hours)
            ]
            articles += dedup(candidates, seen_links, seen_titles, seen_kw)
        if len(articles) >= target:
            print(f"    수집 완료: {len(articles)}개 ({hours}h 이내)")
        elif hours == 24:
            print(f"    24h 기사 {len(articles)}개 → 48h로 확장 시도")

    if len(articles) < target:
        print(f"    [WARN] 최종 {len(articles)}개 수집 (목표 {target}개 미달)")
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

def _build_prompt(batch: list[dict], used_titles: set | None = None) -> str:
    """카테고리별 Gemini 프롬프트 생성 (used_titles: 이미 다른 카테고리에 사용된 키워드)"""
    rules_text = ""
    sections = []
    for entry in batch:
        cat = entry["cat"]
        articles = entry["articles"]
        cid = cat["id"]
        r = CATEGORY_RULES[cid]
        rules_text += f"- {cat['label']}: 포함={r['include']} / 제외={r['exclude']}\n"
        art_text = "\n".join([
            f"  {i+1}. {a['title'].replace(chr(34), chr(39))} | {a['link']}"
            for i, a in enumerate(articles)
        ])
        sections.append(f"[{cat['label']}]\n{art_text}")
    combined = "\n\n".join(sections)
    cat_ids = " / ".join(e["cat"]["id"] for e in batch)

    # 이미 다른 카테고리에 사용된 키워드 목록
    used_note = ""
    if used_titles:
        used_list = ", ".join(f"'{t}'" for t in sorted(used_titles)[:20])
        used_note = f"\n⚠️ 아래 키워드는 이미 다른 카테고리에서 다뤘으므로 이 카테고리에서 절대 포함 금지:\n{used_list}\n"

    cat_id = batch[0]["cat"]["id"]

    # 카테고리별 강화 지시
    extra = ""
    if cat_id == "global_game":
        extra = """
⚠️ 글로벌 게임 카테고리 특별 규칙:
- 펄어비스·넥슨·넷마블·크래프톤·엔씨소프트 등 국내 게임사 기사는 단 1개도 포함 금지.
- '붉은사막' 관련 기사는 제목에 언급만 있어도 전부 제외.
- 반드시 해외 게임사(닌텐도·소니·MS·EA·유비소프트 등)의 기사만 선정."""
    elif cat_id == "it":
        extra = """
⚠️ IT 업계 카테고리 특별 규칙:
- 구글·애플·MS·메타·아마존 등 글로벌 빅테크의 제품·서비스·정책 기사만 선정.
- 국내 반도체 주식 시황, 증권 관련, 박람회 단순 참가 기사는 전부 제외.
- AI 모델·LLM 기술 기사도 제외 (AI 카테고리 담당).
- summary와 reason은 반드시 실제 내용으로 채워야 함. 절대 빈 문자열 금지."""
    elif cat_id == "ai":
        extra = """
⚠️ AI 카테고리 특별 규칙:
- 오픈AI·구글·앤트로픽·MS·메타 등 빅테크의 AI 모델·서비스·전략 기사만 선정.
- 의료·보안·로봇·제조 분야 단순 AI 적용 사례, 박람회·전시회 참가 기사는 전부 제외.
- IT 플랫폼 기획자가 직접 참고할 수 있는 AI 서비스·모델 기사 우선."""

    return f"""당신은 게임/IT 플랫폼 기획자를 위한 뉴스 큐레이터입니다.
{extra}{used_note}

[선정 기준]
{rules_text}
[기사 목록]
{combined}

[지시사항]
1. 선정 기준에 정확히 맞는 기사만 최대 5개 선정. 기준 벗어난 기사는 과감히 제외.
2. 동일 게임·이슈·주제 기사가 여러 개면 가장 대표적인 1개만 선택. 중복 절대 금지.
3. summary: 기사 핵심 내용 2~3줄. 반드시 내용 있게 작성. 빈 문자열 금지.
4. reason: 플랫폼 기획자가 주목해야 할 이유 1~2줄. 반드시 작성. 빈 문자열 금지.
5. title: 영문이면 자연스러운 한국어로 번역. 국문이면 원본 그대로.
6. URL: 절대 새로 생성 금지. 입력된 URL만 사용.

JSON 배열만 출력 (다른 텍스트 금지):
[
  {{
    "category_id": "{cat_ids}",
    "category_insight": "이 카테고리 오늘의 핵심 흐름 1~2문장.",
    "articles": [
      {{
        "title": "한국어 제목",
        "link": "원본 URL 그대로",
        "summary": "기사 핵심 내용 2~3줄 요약 (절대 비우지 말 것)",
        "keywords": ["키워드1", "키워드2", "키워드3"],
        "reason": "기획자가 주목해야 할 이유 1~2줄 (절대 비우지 말 것)"
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
    카테고리별 개별 Gemini 호출 (4회)
    - 배치 묶음 방식 폐기: IT/AI가 같은 배치면 한쪽이 잘리는 문제 해결
    - 호출 간 15초 대기로 rate limit 회피
    - URL 인덱스 매핑으로 Gemini 번역 제목 유지 + URL 원본 보존
    """
    result_map = {}

    for i, entry in enumerate(all_data):
        if i > 0:
            time.sleep(15)
        cat = entry["cat"]
        articles = entry["articles"]
        print(f"    [{i+1}/4] {cat['label']} 분석 중 ({len(articles)}개 기사)...")

        # URL → index 매핑 (Gemini가 URL을 바꿔도 원본 복원용)
        url_to_idx = {a["link"]: idx for idx, a in enumerate(articles)}

        prompt = _build_prompt([entry])
        raw = call_gemini(prompt)
        results_list = _parse_gemini_json(raw)

        for r in results_list:
            # URL 원본 강제 보존 (제목은 Gemini 번역본 유지)
            for art in r.get("articles", []):
                idx = url_to_idx.get(art["link"])
                if idx is not None:
                    art["link"] = articles[idx]["link"]
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
      📬 {TODAY} Daily Brief
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
    msg["Subject"] = f"📬 {TODAY} Daily Brief"
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
    # 전역 seen 세트로 카테고리 간 중복 완전 차단
    global_seen_links  = set()
    global_seen_titles = set()
    global_seen_kw     = set()   # 카테고리 간 키워드 공유 — 동일 주제 교차 중복 차단
    all_data = []
    for cat in CATEGORIES:
        print(f"  ▶ {cat['label']} 기사 수집 중...")
        articles = collect_articles_for_category(
            cat, target=10,
            global_seen_links=global_seen_links,
            global_seen_titles=global_seen_titles,
            global_seen_kw=global_seen_kw,
        )
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
