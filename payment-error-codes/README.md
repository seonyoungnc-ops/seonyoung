# 결제 플랫폼 에러코드 관리

결제 서비스의 에러코드를 JSON 파일로 중앙 관리합니다.

## 빠른 시작

- 에러코드 추가/수정 → 해당 `errors/*.json` 파일 수정 후 PR
- 다대다 매핑 관리 → `mappings/case-mappings.json`
- 자세한 가이드 → [`docs/guide.md`](./docs/guide.md)

## 권역

`K` 한국 · `A` 글로벌 · `T` 대만/홍콩/마카오 · `J` 일본

## 세부 분류

| 파일 | 분류 | 접두사 |
|------|------|--------|
| common.json | 공통 | CMN_ |
| order.json | 주문서 | ORD_ |
| payment.json | 결제 수단 | PAY_ |
| guardian.json | 보호자 동의 | GUARD_ |
| refund.json | 환불/취소 | REFUND_ |
