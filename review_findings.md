# Forie Kids 코드 진단 메모

작성일: 2026-03-15

## 요약

현재 프로젝트는 Flask + Supabase REST 기반의 실사용형 MVP로, 서비스 레이어 분리와 은행 동기화/개인정보 정리/관리자 기능 등이 비교적 잘 구조화되어 있습니다.

다만 현 시점에서는 기능 추가보다 **운영 안정성, 무결성, 보안, 성능 보강**이 우선입니다. 특히 예약 생성, 관리자 인증, 은행 동기화, 캐시 전략에서 운영 환경 기준으로 개선이 필요한 지점이 확인되었습니다.

---

## 우선순위 높은 개선 포인트

### 1. 예약 동시성 및 정원 초과 가능성

관련 파일:

- `app/services/reservation/reservation_record_service.py`
- `app/services/reservation/month_service.py`
- `supabase_schema.sql`

관찰 내용:

- 예약 생성 시 `get_months_with_slots()`로 조회한 캐시/조회 결과를 기준으로 잔여 정원을 계산한 뒤 `insert_row()`를 수행합니다.
- 세대당 1회 제한도 `fetch_rows("reservations", ...)` 결과를 보고 애플리케이션 레벨에서만 검사합니다.
- 이 구조는 동시에 여러 요청이 들어오면 **정원 초과 예약** 또는 **중복 세대 신청**이 발생할 수 있습니다.

리스크:

- 짧은 시간에 여러 사용자가 동시에 신청할 경우 정원 초과 가능
- 동일 세대가 동시에 여러 번 요청하면 중복 예약 가능
- 캐시된 데이터와 실제 DB 상태 사이의 시차 문제 발생 가능

권장 방향:

- Postgres/Supabase 쪽에서 원자적으로 처리되는 RPC 또는 DB 함수 기반 예약 생성으로 변경
- 최소한 `month_id + apt_unit` 기준의 무결성 제약 또는 그에 준하는 보호 장치 검토
- 정원 차감/검사를 DB 트랜잭션 내부에서 수행하도록 구조 전환

---

### 2. 사용자 요청 중 fallback 슬롯 자동 생성

관련 파일:

- `app/services/reservation/reservation_record_service.py`

관찰 내용:

- 활성 슬롯이 없을 때 사용자 예약 요청 흐름 안에서 `reservation_slots`에 기본 슬롯을 생성합니다.
- 생성되는 기본 슬롯은 사실상 비상용 데이터이며 `capacity=9999`로 들어갑니다.

리스크:

- 운영 데이터가 사용자 액션에 의해 예기치 않게 생성됨
- 관리자 의도와 무관한 슬롯 생성 가능
- 데이터 정합성과 운영 정책의 경계가 무너짐

권장 방향:

- 사용자 요청으로 슬롯을 자동 생성하지 않도록 변경
- 슬롯이 없으면 관리자에게 설정 필요 상태를 명확히 보여주고 예약 차단
- 슬롯 생성은 관리자 화면 또는 배치/초기화 로직만 담당

---

### 3. 관리자 인증 보안 부족

관련 파일:

- `app/routes/admin_routes/auth.py`
- `app/routes/admin_routes/decorators.py`
- `config.py`

관찰 내용:

- 관리자 계정은 `.env`의 단일 평문 아이디/비밀번호 기반입니다.
- 로그인 성공 여부는 `session["admin_logged_in"] = True` 플래그로만 관리됩니다.
- 세션 타임아웃, 로그인 시도 제한, IP 기반 보호, 비밀번호 해시 저장이 없습니다.
- `SECRET_KEY`, `ADMIN_PASSWORD` 기본값이 개발용 값으로 남아 있어 운영에서 실수 가능성이 있습니다.

리스크:

- 평문 비밀번호 관리에 따른 보안 위험
- 무차별 대입 공격(bruteforce) 방어 부족
- 운영 환경 설정 누락 시 보안 사고 가능

권장 방향:

- 비밀번호 해시 저장 및 검증 방식으로 전환
- 세션 만료 시간과 재인증 정책 추가
- 로그인 시도 횟수 제한(rate limit) 적용
- 운영 환경에서 기본값 사용 시 앱 시작 실패 또는 강한 경고 처리

---

### 4. 은행 동기화 중복 실행 방지 미흡

관련 파일:

- `app/services/bank/sync_service.py`

관찰 내용:

- 수동 실행과 스케줄 실행이 겹칠 수 있으나, 명시적인 락 또는 중복 실행 방지 장치가 없습니다.
- `bank_sync_runs` 기록은 남기지만, 실행 전 선행 RUNNING 상태 확인이나 advisory lock이 없습니다.

리스크:

- 동일 기간 거래를 동시에 중복 조회
- 상태 갱신 충돌 가능성
- 운영자가 수동 동기화 버튼을 반복 클릭할 때 처리 꼬임 가능

권장 방향:

- 실행 전 `RUNNING` 상태 존재 여부 확인
- 가능하면 DB 락 또는 단일 실행 가드 추가
- 수동 실행 버튼 측에도 재실행 방지 UX 추가

---

## 중간 우선순위 개선 포인트

### 5. 인메모리 TTL 캐시의 멀티워커 일관성 문제

관련 파일:

- `app/services/shared/simple_ttl_cache.py`
- `app/services/reservation/month_service.py`
- `app/services/reservation/content_service.py`
- `README.md`

관찰 내용:

- 캐시가 파이썬 프로세스 메모리에만 저장됩니다.
- README에서는 gunicorn 멀티워커 운영을 권장하고 있습니다.
- 멀티워커 환경에서는 워커마다 캐시가 분리되어 캐시 무효화 결과가 일관되지 않을 수 있습니다.

리스크:

- 어떤 사용자는 최신 데이터, 어떤 사용자는 오래된 데이터를 보게 될 수 있음
- 관리자 수정 후 일부 워커에만 반영되는 문제 가능

권장 방향:

- Redis/Flask-Caching 등 외부 캐시로 전환
- 당장 외부 캐시를 도입하지 않는다면 캐시 TTL 축소 또는 캐시 사용 범위 재검토

---

### 6. Supabase/외부 API 호출 안정성 보강 필요

관련 파일:

- `app/services/supabase_service.py`
- `app/services/bank/api_client.py`
- `app/services/bank/sync_service.py`

관찰 내용:

- 요청마다 새 HTTP 호출을 수행하고, 공통 retry/backoff 전략이 없습니다.
- 네트워크 순간 오류나 타임아웃에 대해 회복 전략이 부족합니다.

리스크:

- 일시적 네트워크 오류에도 즉시 실패
- 외부 API 품질 변동 시 운영 안정성 저하

권장 방향:

- `requests.Session` 재사용
- retry/backoff 정책 추가
- 오류 발생 시 요청 컨텍스트를 충분히 남기도록 로깅 강화

---

### 7. 앱 시작 시 부수효과 실행

관련 파일:

- `app/__init__.py`

관찰 내용:

- 앱 시작 시 `ensure_next_month_reservation()`가 자동 호출됩니다.
- 멀티워커 환경에서는 워커 수만큼 반복 실행될 수 있습니다.

리스크:

- 중복 생성 로직이 완벽히 안전하지 않으면 예기치 않은 데이터 변경 가능
- 앱 시작 시간 지연

권장 방향:

- 앱 startup hook 대신 CLI/cron/systemd timer로 분리
- 최소한 idempotent 보장을 명확히 점검

---

### 8. 관리자 목록 페이지의 전체 조회 구조

관련 파일:

- `app/routes/admin_routes/reservations.py`
- `app/services/admin/reservation_admin_service.py`
- `app/routes/admin_routes/dashboard.py`
- `app/services/admin/bank_admin_service.py`

관찰 내용:

- 예약 목록은 전체 데이터를 매번 조회한 뒤 파이썬에서 필터링합니다.
- `reservations.py`에서는 `list_reservations()`를 한 요청 안에서 두 번 호출합니다.
- 대시보드도 최근 10건 표시를 위해 전체 예약을 먼저 불러온 뒤 슬라이싱합니다.

리스크:

- 데이터가 쌓이면 관리자 화면 응답 속도 저하
- 불필요한 Supabase 호출 증가

권장 방향:

- 서버 측 pagination/filter/search 도입
- count와 목록을 분리하거나 필요한 범위만 조회
- dashboard용 최근 예약 전용 경량 조회 함수 분리

---

### 9. 예외 처리 범위가 너무 넓은 부분 존재

관련 파일 예시:

- `app/services/reservation/month_service.py`
- `app/services/reservation/content_service.py`
- `app/services/admin/bank_admin_service.py`
- 여러 route/service 전반

관찰 내용:

- `except Exception:` 또는 넓은 예외 처리 후 무시하는 패턴이 다수 있습니다.
- 일부는 로깅 없이 조용히 fallback 처리됩니다.

리스크:

- 장애 원인 추적 어려움
- 실제 오류가 숨겨져 품질 저하가 누적될 수 있음

권장 방향:

- 허용 가능한 예외를 구체화
- fallback이 필요한 경우에도 최소한 debug/error 로그 남기기
- 사용자 메시지와 내부 로그를 분리

---

## 데이터베이스/스키마 관점 메모

관련 파일:

- `supabase_schema.sql`

좋은 점:

- `reservation_slot_summary` 뷰 제공
- 주요 FK와 일부 인덱스 존재
- 은행 거래/동기화 로그 테이블이 분리되어 있음

추가 검토 권장 사항:

- `reservations(month_id, apt_unit, status)` 또는 활용 패턴에 맞는 복합 인덱스 검토
- 사용자 조회 패턴이 많다면 `reservations(name, phone, apt_unit)` 계열 인덱스 검토
- 상태값에 대해 CHECK constraint 또는 enum 수준 제약 검토
- `updated_at` 자동 갱신 정책 일관성 검토

---

## 추가하면 좋은 기능 아이디어

### 운영 효율 개선

1. **대기예약(Waitlist)**
   - 마감 후 대기 신청 접수
   - 취소 발생 시 자동 승격

2. **입금대기 자동 리마인드**
   - 일정 시간 내 미입금 사용자에게 알림
   - 예약 누락/문의 감소 효과 기대

3. **감사로그(Audit Log)**
   - 누가 수동 매칭했는지
   - 누가 예약 상태를 바꿨는지
   - 언제 설정이 바뀌었는지 기록

4. **관리자 통계 대시보드 고도화**
   - 월별 신청 수
   - 입금 완료율
   - 미매칭 거래 수
   - 마감 소요 기간 등 시각화

### 사용자 편의 개선

1. **사용자 직접 취소 기능**
   - 일정 시점 전까지 본인 인증 후 취소 허용

2. **신청/입금 상태 안내 강화**
   - 현재 처리 상태를 더 명확히 표시
   - 입금 확인 예상 시간 안내

3. **조회 UX 개선**
   - 비밀번호/예약 조회에서 최근 월 우선 표시
   - 모바일 UX 보강

---

## 추천 실행 순서

### 1차: 필수 안정화

1. 예약 생성 무결성/동시성 보강
2. fallback 슬롯 자동 생성 제거
3. 관리자 인증 강화
4. 은행 동기화 중복 실행 방지

### 2차: 운영 최적화

1. 캐시 구조 개선
2. Supabase/API retry 및 session 재사용
3. 관리자 목록 pagination/filter/search
4. 예외 처리 및 로깅 정리

### 3차: 기능 확장

1. 대기예약
2. 자동 리마인드
3. 감사로그
4. 통계 대시보드 고도화

---

## 최종 결론

현재 프로젝트는 MVP를 넘어 실제 운영에 가까운 흐름을 이미 갖추고 있습니다. 다만 지금은 기능을 더 붙이기보다, **예약 무결성 / 인증 보안 / 동기화 안정성 / 캐시 일관성**을 먼저 다지는 것이 가장 효과적입니다.

이 문서를 기준으로 다음 단계에서는 다음 두 가지 방식 중 하나를 추천합니다.

1. **안정화 패키지 구현**: 위 1차 항목부터 실제 코드/스키마 수정
2. **세부 실행 계획 문서화**: 작업량, 난이도, 영향 범위를 더 세분화한 구현 계획 작성