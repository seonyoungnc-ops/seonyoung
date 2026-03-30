# 결제 플랫폼 에러코드 관리 가이드

## 폴더 구조

```
payment-error-codes/
├── errors/
│   ├── common.json      # 공통 에러 (CMN_xxx)
│   ├── order.json       # 주문서 (ORD_xxx)
│   ├── payment.json     # 결제 수단 (PAY_xxx)
│   ├── guardian.json    # 보호자 동의 (GUARD_xxx)
│   └── refund.json      # 환불/취소 (REFUND_xxx)
├── mappings/
│   └── case-mappings.json  # 에러코드 × Case 다대다 매핑
└── docs/
    └── guide.md
```

## 에러코드 네이밍 규칙

| 분류 | 접두사 | 예시 |
|------|--------|------|
| 공통 | CMN_ | CMN_001 |
| 주문서 | ORD_ | ORD_001 |
| 결제 수단 | PAY_ | PAY_001 |
| 보호자 동의 | GUARD_ | GUARD_001 |
| 환불/취소 | REFUND_ | REFUND_001 |

## JSON 필드 명세

```json
{
  "code": "string",          // 에러 코드 (고유값)
  "name_ko": "string",       // 에러명 (한국어)
  "name_en": "string",       // 에러명 (영어)
  "category": "string",      // 세부 분류
  "http_status": "number",   // HTTP 상태 코드
  "level": "FATAL|ERROR|WARN|INFO",
  "regions": {
    "K": "boolean",          // 한국
    "A": "boolean",          // 글로벌
    "T": "boolean",          // 대만·홍콩·마카오
    "J": "boolean"           // 일본
  },
  "reusable": "boolean",     // 다수 Case 재사용 여부
  "reuse_cases": ["string"], // 재사용되는 Case 목록
  "message_ko": "string",    // 클라이언트 표시 메시지 (KO)
  "message_en": "string",    // 클라이언트 표시 메시지 (EN)
  "cause": "string",         // 원인 요약
  "guide": "string",         // 처리 가이드
  "registered_at": "YYYY-MM-DD",
  "updated_at": "YYYY-MM-DD"
}
```

## 에러코드 추가 프로세스

1. `main` 에서 브랜치 생성: `feature/add-error-PAY_003`
2. 해당 카테고리 JSON 파일에 항목 추가
3. 재사용 에러라면 `mappings/case-mappings.json` 에도 항목 추가
4. PR 생성 → 리뷰 요청 (기획 + 개발 최소 1인 승인)
5. `main` 에 Merge → 웹 뷰어 자동 반영

## 에러 레벨 기준

| 레벨 | 설명 |
|------|------|
| FATAL | 서비스 전체 중단 수준의 심각한 오류 |
| ERROR | 결제 실패 등 사용자 트랜잭션 실패 |
| WARN | 재시도 가능하거나 경고 수준의 이슈 |
| INFO | 정보성 메시지, 비즈니스 로직 분기 처리 |

## 권역 코드

| 코드 | 권역 |
|------|------|
| K | 한국 |
| A | 글로벌 |
| T | 대만 · 홍콩 · 마카오 |
| J | 일본 |
