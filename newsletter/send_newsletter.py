#!/usr/bin/env python3
"""
플랫폼 기획자 데일리 브리프 자동 발송
Google News RSS (트렌딩) + 네이버 뉴스 API (최신) → Gemini 2.5 Flash → Gmail
"""

import os
import re
import json
import smtplib
import urllib.request
import urllib.parse
import urllib.error
import time
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

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
CATEGORY_RULES = {
    "domestic_game": {
        "include": "넥슨·넷마블·크래프톤·펄어비스·엔씨소프트·카카오게임즈·위메이드 등 국내 게임사의 신작·업데이트·매출·유저반응",
        "exclude": "해외 게임사 단독 기사, 주식·증권·시황, AI 기술 자체, 앱 수수료·빅테크 플랫폼 정책(IT 카테고리 담당)",
    },
    "global_game": {
        "include": "해외 게임사의 신작 출시·업데이트·서비스 변화·M&A·기업 전략·실적, 글로벌 게임 시장 트렌드, e스포츠",
        "exclude": "국내 게임사 단독 기사, 주식 시황 단독 기사, 게임 할인·세일 정보, 기념일·N주년 단순 회고",
    },
    "it": {
        "include": "구글·애플·MS·메타·아마존 등 글로벌 빅테크의 신제품·서비스·정책·플랫폼·클라우드·OS 관련 기사",
        "exclude": "게임 단독 기사, AI 모델·LLM 기술 기사(AI 카테고리 담당), 주식·증권·시황, 박람회 단순 참가 소식",
    },
    "ai": {
        "include": "AI 모델·서비스 출시·업데이트, LLM 성능 비교, AI 비즈니스 전략·투자·규제, 오픈AI·구글·앤트로픽·MS·메타 AI 관련 전반",
        "exclude": "게임 단독 기사, 주식·증권·시황 단독 기사",
    },
}

CATEGORIES = [
    {"id": "domestic_game", "label": "🎮 국내 게임 시장", "color": "#c84b31"},
    {"id": "global_game",   "label": "🌐 글로벌 게임 시장", "color": "#2563b0"},
    {"id": "it",            "label": "💻 IT 업계",          "color": "#7c3aed"},
    {"id": "ai",            "label": "🤖 AI",               "color": "#0891b2"},
]

# 단일 키워드 중심 — 한글+영문 병행으로 수집 커버리지 극대화
BASE_QUERIES = {
    # 국내 게임: 국내 게임사명 위주 (한글)
    "domestic_game": [
        "넥슨","넷마블","크래프톤","펄어비스","엔씨소프트",
        "카카오게임즈","위메이드","컴투스","스마일게이트","시프트업",
        "넥슨게임즈","카카오게임",
    ],
    # 글로벌 게임: 회사별 교차 배치 (한글+영문 연속 배치 방지)
    "global_game": [
        "닌텐도","플레이스테이션","Xbox","유비소프트",
        "블리자드","에픽게임즈","스팀","EA게임",
        "Nintendo","PlayStation","엑스박스","Ubisoft",
        "Blizzard","Epic Games","Steam","Valve",
    ],
    # IT: 회사별로 교차 배치 → 특정 회사 기사 독점 방지
    # 순서: 애플→구글→MS→메타→아마존→삼성→빅테크 순환
    "it": [
        "애플","구글","마이크로소프트","메타","아마존",
        "삼성전자","Apple","Google","Microsoft","Meta",
        "Amazon","Samsung","빅테크","클라우드","iPhone",
    ],
    # AI: 회사별 교차 배치 → 오픈AI 독점 방지
    # 순서: 오픈AI→구글→앤트로픽→MS→메타→딥시크→퍼플렉시티→xAI 순환
    "ai": [
        "챗GPT","제미나이","클로드","코파일럿",
        "딥시크","퍼플렉시티","그록","생성형AI",
        "ChatGPT","Gemini","Claude","Copilot",
        "OpenAI","Anthropic","DeepSeek","Grok",
        "LLM","AI모델","Llama","xAI",
    ],
}



# 글로벌 게임 전용 RSS
GLOBAL_GAME_RSS = [
    "https://feeds.feedburner.com/ign/games-all",
    "https://www.gamespot.com/feeds/mashup/",
    "https://www.eurogamer.net/?format=rss",
    "https://www.pcgamer.com/rss/",
    "https://kotaku.com/rss",
    "https://www.videogameschronicle.com/feed/",
    "https://www.gamesradar.com/rss/",
]

# 네이버 많이 본 뉴스 — 카테고리별 섹션 ID
# 101=경제, 105=IT/과학, 103=생활/문화, 섹션 없는 게임은 105로 대체
NAVER_POPULAR_SECTIONS = {
    "domestic_game": ["105"],        # IT/과학 (게임 포함)
    "global_game":   ["105"],        # IT/과학 (게임 포함)
    "it":            ["105", "101"], # IT/과학 + 경제
    "ai":            ["105"],        # IT/과학
}

# ──────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────
def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").replace("&quot;",'"').replace("&amp;","&").replace("&#39;","'").strip()

def normalize_title(title: str) -> str:
    return re.sub(r"[^a-zA-Z0-9가-힣]", "", title).lower()

def is_within_hours(pub: str, hours: int = 24) -> bool:
    """pubDate 파싱 실패 시 False 반환 — 날짜 불명 기사 제외"""
    if not pub or not pub.strip():
        return False  # pubDate 없으면 제외
    # RFC 2822 (네이버/Google News 공통 형식)
    try:
        dt = parsedate_to_datetime(pub)
        return (datetime.now(timezone.utc) - dt).total_seconds() <= hours * 3600
    except Exception:
        pass
    # ISO 8601 형식 시도 (일부 RSS)
    try:
        pub_clean = pub.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(pub_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() <= hours * 3600
    except Exception:
        return False  # 파싱 실패 시 제외 (오래된 기사 섞임 방지)

def http_get(url: str, headers: dict = None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()

# ──────────────────────────────────────────────
# 1-A. Google Trends 급상승 키워드 수집
# ──────────────────────────────────────────────
# Google News RSS — 카테고리별 키워드 검색 피드
# 형식: https://news.google.com/rss/search?q=KEYWORD&hl=ko&gl=KR&ceid=KR:ko
GOOGLE_NEWS_QUERIES = {
    "domestic_game": ["넥슨 게임", "넷마블 게임", "크래프톤", "펄어비스", "엔씨소프트", "카카오게임즈"],
    "global_game":   ["Nintendo game", "PlayStation game", "Xbox game", "Steam game release", "Ubisoft", "Blizzard game"],
    "it":            ["Apple 애플", "Google 구글", "Microsoft 마이크로소프트", "Meta 메타", "Samsung 삼성전자"],
    "ai":            ["ChatGPT OpenAI", "Gemini Google AI", "Claude Anthropic", "생성형AI LLM", "AI 모델 출시", "딥시크 DeepSeek", "퍼플렉시티 Perplexity", "그록 Grok xAI"],
}

def resolve_google_news_url(google_url: str) -> str:
    """
    Google News 리다이렉션 URL → 실제 원본 URL
    1순위: description href 파싱
    2순위: GET 요청으로 리다이렉션 추적
    """
    # GET 요청으로 리다이렉션 추적 (브라우저 UA 사용)
    try:
        req = urllib.request.Request(google_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        with opener.open(req, timeout=8) as resp:
            final_url = resp.url
            if "news.google.com" not in final_url:
                return final_url
    except Exception:
        pass
    return google_url

def extract_url_from_description(desc_html: str) -> str:
    """Google News RSS description에서 실제 기사 URL 추출"""
    # news.google.com 제외한 첫 번째 href
    matches = re.findall(r'href="(https?://[^"]+)"', desc_html)
    for url in matches:
        if "news.google.com" not in url:
            return url
    return ""

def fetch_google_news_rss(query: str, max_items: int = 10) -> list[dict]:
    """Google News RSS 키워드 검색 — 실제 기사 URL 추출"""
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        raw = http_get(url)
        root = ET.fromstring(raw)
        items = []
        for item in root.findall(".//item")[:max_items]:
            title    = clean_html(item.findtext("title") or "")
            pub      = (item.findtext("pubDate") or "").strip()
            desc_raw = item.findtext("description") or ""
            google_link = (item.findtext("link") or "").strip()

            # 1순위: description href에서 추출
            orig_url = extract_url_from_description(desc_raw)

            # 2순위: 리다이렉션 추적
            if not orig_url and google_link:
                orig_url = resolve_google_news_url(google_link)

            # 그래도 구글 URL이면 스킵 (접근 불가 링크 제외)
            if not orig_url or "news.google.com" in orig_url:
                continue

            desc = clean_html(desc_raw)[:120]
            if title:
                items.append({"title": title, "link": orig_url,
                              "description": desc, "pubDate": pub})
        if items:
            print(f"    [DEBUG] pubDate 샘플: {items[0].get('pubDate','없음')}")
        return items
    except Exception as e:
        print(f"    [WARN] Google News RSS '{query}': {e}")
        return []



# ──────────────────────────────────────────────
# 1-B. 네이버 많이 본 뉴스 크롤링
# ──────────────────────────────────────────────





# ──────────────────────────────────────────────
# 1-C. 네이버 뉴스 API
# ──────────────────────────────────────────────
def fetch_naver_popular(section_id: str) -> list[dict]:
    """
    네이버 뉴스 섹션별 '많이 본 뉴스' 크롤링
    https://news.naver.com/section/ranking/popular?sid={section_id}
    → 실제 독자 클릭수 기반 인기 기사 반환
    """
    url = f"https://news.naver.com/section/ranking/popular?sid={section_id}"
    try:
        raw = http_get(url, {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://news.naver.com",
        }).decode("utf-8", errors="ignore")

        articles = []
        seen = set()

        # 기사 제목+링크 패턴 추출
        # 네이버 뉴스 많이 본 뉴스 HTML에서 링크와 제목 파싱
        pattern = r'href="(https://n\.news\.naver\.com/[^"]+)"[^>]*>\s*([^<]{5,100})</a>'
        for m in re.finditer(pattern, raw):
            link  = m.group(1).strip()
            title = clean_html(m.group(2)).strip()
            if not title or not link or link in seen:
                continue
            if len(title) < 5:
                continue
            seen.add(link)
            articles.append({"title": title, "link": link,
                              "description": "", "pubDate": ""})
            if len(articles) >= 20:
                break

        # 패턴이 안 잡히면 대안 패턴 시도
        if not articles:
            pattern2 = r'data-rank-title="([^"]{5,100})"[^>]*data-rank-oid[^>]*href="([^"]+)"'
            for m in re.finditer(pattern2, raw):
                title = clean_html(m.group(1)).strip()
                link  = m.group(2).strip()
                if not title or not link or link in seen:
                    continue
                seen.add(link)
                articles.append({"title": title, "link": link,
                                  "description": "", "pubDate": ""})
                if len(articles) >= 20:
                    break

        print(f"    많이 본 뉴스 (sid={section_id}): {len(articles)}개")
        return articles
    except Exception as e:
        print(f"    [WARN] 많이 본 뉴스 크롤링 실패 (sid={section_id}): {e}")
        return []

def fetch_naver_news(query: str, display: int = 20) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display={display}&sort=sim"
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("items", [])
    except Exception as e:
        print(f"    [WARN] Naver API '{query}': {e}")
        return []

# ──────────────────────────────────────────────
# 1-C. RSS 수집 (글로벌 게임용)
# ──────────────────────────────────────────────
def fetch_rss(url: str, max_items: int = 20) -> list[dict]:
    try:
        raw = http_get(url)
        root = ET.fromstring(raw)
        items = []
        for item in root.findall(".//item")[:max_items]:
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link") or "").strip()
            desc  = clean_html(item.findtext("description") or "")[:120]
            if title and link:
                items.append({"title": title, "link": link, "description": desc, "pubDate": ""})
        if not items:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//a:entry", ns)[:max_items]:
                title = (entry.findtext("a:title", namespaces=ns) or "").strip()
                link_el = entry.find("a:link", ns)
                link = (link_el.get("href","") if link_el is not None else "").strip()
                desc = clean_html(entry.findtext("a:summary", namespaces=ns) or "")[:120]
                if title and link:
                    items.append({"title": title, "link": link, "description": desc, "pubDate": ""})
        return items
    except Exception as e:
        print(f"    [WARN] RSS {url[:50]}: {e}")
        return []

# ──────────────────────────────────────────────
# 1-D. 카테고리별 기사 수집
# ──────────────────────────────────────────────
def collect_articles_for_category(cat: dict) -> list[dict]:
    """
    수집 전략:
    1순위: 네이버 많이 본 뉴스 크롤링 (실제 클릭수 기반)
    2순위: 네이버 API (키워드별 균등 2개씩, 24h 이내)
           5개 미달 시 48h 자동 확장
    결과: 1순위 먼저 배치, 나머지는 Gemini가 보충 선별
    """
    seen_links = set()
    seen_norms = set()
    cat_id     = cat["id"]
    PER_QUERY  = 2

    def try_add(title, link, desc, pub="", hours=48) -> dict | None:
        norm = normalize_title(title)
        if not link or link in seen_links or norm in seen_norms:
            return None
        if pub and not is_within_hours(pub, hours):
            return None
        seen_links.add(link)
        seen_norms.add(norm)
        return {"title": title, "link": link, "description": desc, "pubDate": pub}

    def collect_from_queries(queries, hours) -> list[dict]:
        """
        1라운드: 모든 키워드에서 1개씩 순환 수집 → 뒷 키워드 누락 방지
        2라운드: 여전히 부족하면 각 키워드에서 추가 수집
        """
        result = []
        # 1라운드: 전 키워드 1개씩
        for q in queries:
            for item in fetch_naver_news(q, display=20):
                a = try_add(
                    clean_html(item.get("title","")),
                    item.get("originallink") or item.get("link",""),
                    clean_html(item.get("description",""))[:120],
                    item.get("pubDate",""), hours
                )
                if a:
                    result.append(a)
                    break  # 키워드당 1개만
        # 2라운드: 추가 수집 (각 키워드에서 1개 더)
        for q in queries:
            count = 0
            for item in fetch_naver_news(q, display=20):
                a = try_add(
                    clean_html(item.get("title","")),
                    item.get("originallink") or item.get("link",""),
                    clean_html(item.get("description",""))[:120],
                    item.get("pubDate",""), hours
                )
                if a:
                    count += 1
                    result.append(a)
                if count >= 1:
                    break
        return result

    def collect_from_rss(hours) -> list[dict]:
        result = []
        for feed_url in GLOBAL_GAME_RSS:
            count = 0
            for item in fetch_rss(feed_url):
                if count >= PER_QUERY:
                    break
                a = try_add(item["title"], item["link"], item["description"], "", hours)
                if a:
                    result.append(a)
                    count += 1
        return result

    def collect_gnews(hours):
        result = []
        queries = GOOGLE_NEWS_QUERIES.get(cat_id, [])
        # 1라운드: 전 키워드 1개씩 순환
        for q in queries:
            for item in fetch_google_news_rss(q, max_items=5):
                a = try_add(item["title"], item["link"], item["description"], item["pubDate"], hours)
                if a:
                    result.append(a)
                    break
        # 2라운드: 추가 수집
        for q in queries:
            count = 0
            for item in fetch_google_news_rss(q, max_items=5):
                a = try_add(item["title"], item["link"], item["description"], item["pubDate"], hours)
                if a:
                    result.append(a)
                    count += 1
                if count >= 1:
                    break
        return result

    # ── 1순위: Google News RSS ──
    gnews_articles = collect_gnews(24)

    # ── 2순위: 네이버 API ──
    api_articles = []
    if cat_id == "global_game":
        api_articles += collect_from_rss(24)
    api_articles += collect_from_queries(BASE_QUERIES.get(cat_id, []), 24)

    # 5개 미달이면 48h 확장
    total = len(gnews_articles) + len(api_articles)
    if total < 5:
        print(f"    24h {total}개 → 48h 확장")
        gnews_articles += collect_gnews(48)
        if cat_id == "global_game":
            api_articles += collect_from_rss(48)
        api_articles += collect_from_queries(BASE_QUERIES.get(cat_id, []), 48)

    articles = gnews_articles + api_articles
    print(f"    수집 완료: {len(articles)}개 (GoogleNews: {len(gnews_articles)}, NaverAPI: {len(api_articles)})")
    return articles


# ──────────────────────────────────────────────
# 어제 발송 기사 중복 제거 (GitHub Actions Artifacts)
# ──────────────────────────────────────────────

def load_yesterday_articles() -> set:
    """
    GitHub Actions API로 어제 artifact(sent_articles.json)에서
    발송된 기사 URL + 정규화 제목 세트 로드
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    repo  = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        print("    [INFO] GITHUB_TOKEN/REPOSITORY 없음 — 중복 제거 스킵")
        return set()
    try:
        import zipfile, io
        # 최근 artifact 목록 조회
        api_url = f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=10&name=sent-articles"
        req = urllib.request.Request(api_url, headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        artifacts = [a for a in data.get("artifacts", []) if not a.get("expired", True)]
        if not artifacts:
            print("    [INFO] 어제 artifact 없음 — 중복 제거 스킵")
            return set()
        latest = artifacts[0]
        dl_url = latest["archive_download_url"]
        req2 = urllib.request.Request(dl_url, headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urllib.request.urlopen(req2, timeout=15) as resp:
            zdata = resp.read()
        with zipfile.ZipFile(io.BytesIO(zdata)) as z:
            with z.open("sent_articles.json") as f:
                yesterday = json.loads(f.read())
        seen = set()
        for art in yesterday:
            seen.add(art.get("link", ""))
            seen.add(normalize_title(art.get("title", "")))
        print(f"    [INFO] 어제 발송 기사 {len(yesterday)}개 로드 — 중복 제거 적용")
        return seen
    except Exception as e:
        print(f"    [WARN] 어제 기사 로드 실패: {e} — 중복 제거 스킵")
        return set()

def save_today_articles(category_results: list[dict]):
    """오늘 발송한 기사 목록을 sent_articles.json으로 저장"""
    articles = []
    for cr in category_results:
        for art in cr["analyzed"].get("articles", []):
            articles.append({"link": art.get("link",""), "title": art.get("title","")})
    path = "newsletter/sent_articles.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"    오늘 발송 기사 {len(articles)}개 저장 → {path}")

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
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            wait = 30 * (2 ** attempt)
            print(f"    [WARN] Gemini 오류 (시도 {attempt+1}/{retries}): {e} → {wait}초 후 재시도")
            if attempt < retries - 1:
                time.sleep(wait)
            else:
                raise

def build_prompt(batch: list[dict]) -> str:
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

    combined = "\n\n".join(sections)
    cat_ids  = " / ".join(e["cat"]["id"] for e in batch)

    extra = ""
    if any(e["cat"]["id"] == "domestic_game" for e in batch):
        extra += "\n⚠️ 국내 게임: 국내 게임사의 신작·업데이트·매출·서비스 기사만. 앱 수수료·빅테크·IT 정책 기사는 IT 업계 카테고리 담당이므로 포함 금지."
    if any(e["cat"]["id"] == "global_game" for e in batch):
        extra += "\n⚠️ 글로벌 게임: 국내 게임사(넥슨·넷마블·크래프톤·펄어비스 등) 기사 포함 금지. 단순 할인·세일, 기념일 회고, 개인 체험기·사용기, 팁/가이드 기사 제외. 신작·서비스·전략·M&A·시장 동향 기사만. 5개 목표."
    if any(e["cat"]["id"] == "it" for e in batch):
        extra += "\n⚠️ IT 업계: 빅테크 신제품·서비스·정책 기사 우선. 주식·시황 단독 기사 제외. 5개 채우기 위해 IT 관련 기사라면 포함."
    if any(e["cat"]["id"] == "ai" for e in batch):
        extra += "\n⚠️ AI: AI 모델·서비스·전략 관련 기사 우선. 게임·주식 단독 기사만 제외. 5개 채우기 위해 AI 관련 기사라면 포함."

    return f"""당신은 게임/IT 플랫폼 기획자를 위한 뉴스 큐레이터입니다.
{extra}

[카테고리별 선정 기준]
{rules_text}
[기사 목록]
{combined}

[지시사항]
1. 각 카테고리에서 선정 기준에 맞는 기사 5개 선정을 목표로 함.
   - 기준에 완벽히 맞는 기사가 5개 미만이면, 해당 카테고리와 관련성이 조금이라도 있는 기사로 채워서 반드시 5개를 맞출 것.
   - 억지로 채우는 것보다 품질이 중요하지만, 3개 이하는 절대 허용 안 됨.
2. 동일 게임·이슈·주제 기사가 여러 개면 가장 핵심적인 1개만 선택.
3. category_insight: 반드시 2문장 이내. 3문장 이상 절대 금지.
4. summary: 기사 핵심 내용 2~3줄. 절대 비우지 말 것.
5. insight: 시장에서 무슨 일이 일어나고 있는지, 그게 왜 중요한지를 2줄 이내로 서술. 다음 표현 절대 금지: "플랫폼 기획 시", "기획자는", "기획자가", "확인해야", "참고해야", "고려해야", "활용할 수 있". 주어 없이 시장 현상과 그 의미만 담을 것. 절대 비우지 말 것.
6. title: 국문 기사는 원본 그대로, 영문이면 한국어로 번역.
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
        "insight": "기획·전략·의사결정 활용 관점 2줄 이내 (구체적 액션/판단 근거)"
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
    """2배치 호출: [국내+글로벌] / [IT+AI]"""
    result_map = {}
    batches = [all_data[:2], all_data[2:]]
    for i, batch in enumerate(batches):
        if i > 0:
            time.sleep(20)
        labels = " + ".join(e["cat"]["label"] for e in batch)
        total  = sum(len(e["articles"]) for e in batch)
        print(f"    [{i+1}/2] {labels} 분석 중 (총 {total}개)...")
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
                  <td style="width:52px;padding:3px 0;">{label('인사이트')}</td>
                  <td style="padding:3px 0;font-size:13px;color:#4a4a47;font-family:{BASE_FONT};line-height:1.6;">{art.get('insight','')}</td>
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
# Gmail 발송
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

    # 어제 발송 기사 로드 (중복 제거용)
    print("  ▶ 어제 발송 기사 로드 중...")
    yesterday_seen = load_yesterday_articles()

    # 카테고리별 기사 수집 — 어제 기사 제외 후 최대 12개 전달
    all_data = []
    for cat in CATEGORIES:
        print(f"  ▶ {cat['label']} 기사 수집 중...")
        articles = collect_articles_for_category(cat)
        # 어제 발송 기사 제외
        if yesterday_seen:
            before = len(articles)
            articles = [
                a for a in articles
                if a["link"] not in yesterday_seen
                and normalize_title(a["title"]) not in yesterday_seen
            ]
            print(f"    어제 기사 제외: {before}개 → {len(articles)}개")
        all_data.append({"cat": cat, "articles": articles[:12]})

    # Gemini 분석
    print("  ▶ Gemini 분석 중...")
    result_map = analyze_all_categories(all_data)
    print("    분석 완료")

    # HTML 생성
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

    # 오늘 발송 기사 저장 (내일 중복 제거용)
    save_today_articles(category_results)
    print("[완료] 데일리 브리프 발송 성공!")

if __name__ == "__main__":
    main()
