# 에러 코드 관리 프로젝트

## 레포지토리
- GitHub: `seonyoungnc-ops/seonyoung`
- 작업 디렉토리: `C:\Users\seonyoung\AppData\Local\Temp\seonyoung\claude-code`
- 브랜치: `main`

## 주요 파일
| 파일 | 설명 |
|------|------|
| `error-codes.json` | 에러 코드 정의 (현재 390개 항목) |
| `docs/error-codes/index.html` | GitHub Pages 웹 뷰어 |
| `docs/index.html` | `/error-codes/`로 리다이렉트 |

## 원본 소스
- 엑셀 파일: `C:\Users\seonyoung\Downloads\오류 코드 정의(복구) (1).xlsx`
- 시트 목록: 공통, 통합샵, 송금, QR코드, 충전결제, NCAPAY, 선물함|구매내역, 쿠폰함, 설정, 정기결제 관리, 부가서비스, 유료결제보호자동의

## JSON 스키마
```json
{
  "errorCode": 12345,          // 숫자 코드 (엑셀 서브코드)
  "systemCode": "GWA00",       // 영숫자 코드 (엑셀 부모코드, 선택)
  "type": "NET_ERR_...",       // 타입 상수 (선택)
  "service": "공통",            // 서비스명
  "cause": "원인 설명",         // 원인
  "message": "유저 노출 메시지"  // 에러 메시지
}
```
- `guide` 필드: 엑셀 원본에 없는 항목은 미포함
- 기존 `code` 필드(1001~6001) 항목은 원본 미포함으로 삭제됨

## 웹 뷰어
- URL: `https://seonyoungnc-ops.github.io/seonyoung/error-codes/`
- JSON을 GitHub Raw URL에서 직접 fetch → push 즉시 반영
- Raw URL: `https://raw.githubusercontent.com/seonyoungnc-ops/seonyoung/main/claude-code/error-codes.json`

## Figma 디자인
- URL: `https://www.figma.com/design/SwQN6WsvLUjW8LlQiHy9H5/🚀-선영?node-id=141-3257`
- 에러 코드 관리 테이블 화면 (node-id: 141:3257, 프레임: 142:96)
- 컬럼: 코드 / 타입 / 서비스 / 메시지 / 원인 / 가이드
- 디자인 특징: 남색 GNB(#2d2f6e), 연보라 테이블 헤더(#eef0f8), 보라 가이드 칩

## HTML 컬럼 너비 (현재)
```css
col.c-code   { width: 88px }
col.c-type   { width: 280px }
col.c-svc    { width: 110px }
col.c-msg    { width: 380px }
col.c-cause  { width: 220px }
col.c-guide  { width: 280px }
```

## 작업 히스토리 요약
1. 엑셀 12개 시트 파싱 → JSON 변환 (Node.js, xlsx 패키지)
2. Figma 디자인 기반 HTML 웹 뷰어 구축 → GitHub Pages 배포
3. 알파벳+숫자 혼합 코드(GWA*, GSE* 등) 포함 / 제외 작업 반복 → 현재 **포함** 상태
4. 빈 메시지 33개 → 부가서비스 시트 원본 문장으로 채움
5. 멀티라인 메시지(SUA01, GWA00 등) 단일 메시지로 통합
6. 유료결제보호자동의 시트 재매핑 (Code→errorCode, Description→cause, 에러메세지→message)
7. 합산 오류 코드(1000100120007000, 833138313383142 등) 삭제

## 주의사항
- 엑셀 파싱 시 Node.js 경로: `node` (bash 환경)
- xlsx 패키지 경로: `C:/Users/seonyoung/AppData/Roaming/npm/node_modules/xlsx`
- git 작업 디렉토리: `C:\Users\seonyoung\AppData\Local\Temp\seonyoung\claude-code`
- 레포 루트: `C:\Users\seonyoung\AppData\Local\Temp\seonyoung` (GitHub Pages는 루트의 `docs/` 폴더 기준)
- HTML 수정 후 레포 루트 `docs/error-codes/index.html`에도 복사 필요
