# 에러 코드 처리 로직

## 에러 코드 구조

```ts
interface ErrorCode {
  code    : number;      // 숫자 코드 (예: 1001)
  type    : string;      // ERROR_CASE_NAME 형식 (예: AUTH_TOKEN_EXPIRED)
  service : string;      // 서비스 도메인 (인증 | 결제 | 공통 | 주문서 | 지갑)
  message : string;      // 사용자 노출 메시지 (2줄: 상황 + 안내)
  cause   : string;      // 내부 발생 원인
  guide   : GuideItem[]; // 버튼 및 처리 방식 (1~2개)
}

interface GuideItem {
  button: string; // UI 버튼 레이블
  action: string; // 클릭 시 처리 방식 설명
}
```

---

## 코드 번호 대역

| 대역      | 서비스        |
|-----------|---------------|
| 1000~1999 | 인증          |
| 2000~2999 | 결제          |
| 3000~3999 | 공통 (네트워크) |
| 4000~4999 | 공통 (시스템)  |
| 5000~5999 | 주문서        |
| 6000~6999 | 지갑          |

---

## 처리 흐름

```
서버/클라이언트에서 오류 발생
        │
        ▼
error-codes.json에서 code 조회
        │
        ├── 코드 존재 → message 노출 + guide 버튼 렌더링
        │                     │
        │                     └── 버튼 클릭 → action 처리
        │                           ├── 페이지 이동
        │                           ├── 재요청
        │                           └── 팝업 닫기
        │
        └── 코드 없음 → fallback: SYSTEM_INTERNAL_ERROR (4001)
```

---

## 가이드 버튼 처리 원칙

- 버튼은 **1개 또는 2개**로 구성
- 첫 번째 버튼: 주요 액션 (재시도, 이동, 확인)
- 두 번째 버튼: 보조 액션 (취소, 닫기)
- 버튼 클릭 후 오류 상태 초기화

---

## 데이터 관리 방식

- `error-codes.json`을 **GitHub 저장소**에서 관리
- 수정/추가는 PR을 통해 리뷰 후 병합
- 관리 페이지는 Read-only (조회 전용)
- 배포 파이프라인을 통해 자동 반영

---

## 서비스별 주요 에러 타입

| 서비스  | 에러 타입 |
|---------|-----------|
| 인증    | TOKEN_EXPIRED, INVALID_CREDENTIALS, ACCESS_DENIED |
| 결제    | PROCESS_FAILED, DUPLICATE_DETECTED, INSUFFICIENT_BALANCE, METHOD_UNSUPPORTED |
| 공통    | CONNECTION_FAILED, REQUEST_TIMEOUT, INTERNAL_ERROR, MAINTENANCE |
| 주문서  | NOT_FOUND, EXPIRED, INVALID_STATUS |
| 지갑    | INSUFFICIENT_FUNDS |
