# AI 용어 학습 및 Claude ↔ GitHub MCP 연결

> 이 폴더는 Claude와의 대화 기록 및 GitHub MCP 연결 가이드를 담고 있습니다.

---

## 📋 대화 요약

| 항목 | 내용 |
|------|------|
| 날짜 | 2026-03-27 |
| 레포지토리 | seonyoungnc-ops/seonyoung |
| 주요 내용 | GitHub MCP 연결 테스트, 이슈 생성, 파일 Push |

**이 대화에서 확인한 것:**
- ✅ Claude → GitHub 이슈 생성 성공 ([#1](https://github.com/seonyoungnc-ops/seonyoung/issues/1))
- ✅ Claude → GitHub 파일 Push 성공
- ✅ Claude ↔ GitHub MCP 연결 정상 동작 확인

---

## 🔧 Claude Desktop에서 GitHub MCP 연결하기

### Step 1 — GitHub Personal Access Token 발급

1. [github.com](https://github.com) → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. **Generate new token (classic)** 클릭
3. 필요한 권한 선택:

   | 권한 | 설명 |
   |------|------|
   | `repo` (전체) | 레포지토리 읽기/쓰기 |
   | `workflow` | GitHub Actions 워크플로우 |
   | `read:org` | 조직 정보 읽기 |

4. **Generate token** 클릭 후 생성된 토큰(`ghp_...`) 복사 → 안전한 곳에 보관

> ⚠️ 토큰은 생성 직후 한 번만 보여집니다. 반드시 복사해두세요.

---

### Step 2 — Claude Desktop 설정 파일 열기

| OS | 경로 |
|----|------|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |

터미널에서 바로 열기:
```bash
# macOS
open ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows (PowerShell)
notepad $env:APPDATA\Claude\claude_desktop_config.json
```

---

### Step 3 — 설정 파일에 MCP 서버 추가

`claude_desktop_config.json` 파일을 아래와 같이 수정:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

> `ghp_YOUR_TOKEN_HERE` 자리에 Step 1에서 발급받은 실제 토큰을 입력하세요.

---

### Step 4 — Claude Desktop 재시작 후 연결 확인

1. Claude Desktop 완전히 종료 후 재시작
2. 채팅창 우하단에 🔧 **MCP 아이콘** 표시되면 연결 성공
3. 아래처럼 요청해서 동작 확인:

```
seonyoungnc-ops/seonyoung 레포 이슈 목록 보여줘
```

---

### 사전 조건

- **Node.js** 설치 필요
  ```bash
  node -v  # 버전 확인
  ```
  미설치 시 [nodejs.org](https://nodejs.org) 에서 LTS 버전 설치

- `npx`가 자동으로 `@modelcontextprotocol/server-github` 패키지를 설치합니다

---

## 📁 파일 목록

| 파일 | 설명 |
|------|------|
| `README.md` | 이 파일 — 가이드 및 대화 요약 |
| `대화전문.md` | 대화 전체 내용 |
