# AI 용어 학습 및 Claude <-> GitHub MCP 연결

**날짜:** 2026-03-27  
**참여자:** 사용자, Claude (Sonnet 4.6)

---

## 📌 대화 요약

이 대화에서는 Claude Desktop에서 GitHub MCP(Model Context Protocol)를 연결하고, 실제로 GitHub 이슈를 생성하는 테스트를 진행했습니다.

---

## 🗣️ 전체 대화 내용

### 1. GitHub 이슈 생성 요청

**사용자:**
> seonyoungnc-ops/seonyoung 레포에 GitHub 이슈 만들어줘  
> 제목: AI 용어 학습 및 Claude <-> GitHub MCP 연결  
> 내용: 테스트

**Claude:**
GitHub MCP 툴(`github:create_issue`)을 사용하여 이슈 생성 실행.

✅ **결과:**
- 이슈 번호: #1
- 링크: https://github.com/seonyoungnc-ops/seonyoung/issues/1
- Claude ↔ GitHub MCP 연결 정상 동작 확인

---

### 2. Claude 폴더 생성 + 이슈 제목으로 파일 업로드 요청

**사용자:**
> 지금 이 대화 내용을 레포 내 Claude 폴더를 생성한 뒤, 제목: AI 용어 학습 및 Claude <-> GitHub MCP 연결 으로 올려줘. 대화 내용 확인이 전체 가능해야하고, Claude Desktop에서 깃허브 MCP 연결하는법 이미지로 만들어서 함께 첨부해줘

**Claude:**
1. GitHub MCP 연결 방법 안내 이미지를 SVG로 생성 (4단계 가이드)
2. SVG → PNG 변환 (cairosvg 사용)
3. 마크다운 문서(이 파일) + PNG 이미지를 `Claude/` 폴더에 push

---

## 🔗 Claude Desktop에서 GitHub MCP 연결하는 법

> 📎 첨부 이미지 참고: `github_mcp_setup_guide.png`

![GitHub MCP 연결 가이드](github_mcp_setup_guide.png)

### Step 1 — Claude Desktop 설정 파일 열기

| OS | 경로 |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

파일이 없다면 직접 생성합니다 (Claude Desktop 설치 후 자동 생성되기도 함).

---

### Step 2 — GitHub Personal Access Token 발급

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. "Generate new token (classic)" 클릭
3. 권한(scope) 선택: `repo`, `read:org`, `workflow`
4. 생성된 토큰(ghp_...)을 안전한 곳에 복사해 저장

> ⚠️ 토큰은 한 번만 표시됨 — 즉시 저장 필수

---

### Step 3 — config 파일에 GitHub MCP 서버 추가

아래 내용을 `claude_desktop_config.json`에 붙여넣기:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_여기에_토큰입력"
      }
    }
  }
}
```

---

### Step 4 — Claude Desktop 재시작 및 확인

1. Claude Desktop을 완전히 종료 후 재실행
2. 채팅창에서 "내 GitHub 레포 목록 보여줘" 등 테스트
3. MCP 연결 확인 ✅

> 연결 성공 시 Claude가 GitHub 이슈·PR·파일 생성 등을 직접 수행 가능

---

## ✅ 이번 대화 결과물

| 항목 | 내용 |
|---|---|
| GitHub 이슈 #1 | https://github.com/seonyoungnc-ops/seonyoung/issues/1 |
| 업로드 폴더 | `Claude/` |
| 업로드 파일 | `AI_용어학습_Claude_GitHub_MCP_연결.md`, `github_mcp_setup_guide.png` |

---

*이 문서는 Claude (claude-sonnet-4-6)가 작성했습니다.*
