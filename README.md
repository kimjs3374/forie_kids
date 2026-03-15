# 아파트 어린이 놀이터 월별 예약 관리 시스템

Flask + Supabase REST + Jinja2 기반 운영형 예약 시스템입니다. 개발은 Windows에서도 가능하지만, **실제 운영 환경은 Ubuntu** 기준으로 구성합니다.

현재 문서는 **v2.0 기준**으로 정리되어 있으며, 주요 변경사항은 `forie_kdis_releasenote.md`에서도 확인할 수 있습니다.

---

## 1. v2.0 주요 기능 요약

### 사용자 기능

- 월별 놀이터 이용 신청
- 신청 조회 / 입금확인 여부 조회
- 월별 입장 비밀번호 조회
- 문의사항 등록 및 답변 조회
- 신청 완료 후 입금금액/계좌정보 안내 모달 제공
- 계좌번호 복사 버튼 지원
- 월 이용금액이 `0원`인 경우 자동 예약완료 처리

### 관리자 기능

- 예약 월 생성 / 수정 / 삭제
- 월별 이용금액 직접 관리
- 예약현황 및 입금확인 관리
- 문의사항 관리 및 답변 등록/수정/삭제
- 은행 연동 및 입금 수집/매칭 관리
- 전광판 / 공지 / 도움말 운영 지원

### 운영/백엔드 기능

- Supabase REST API 기반 데이터 관리
- 예약 생성 RPC(`create_reservation_atomic`) 사용
- 개인정보 보관기간 지난 데이터 정리 CLI 제공
- 은행 거래 동기화 CLI 제공
- 문의사항 데이터 구조(`inquiries`, `inquiry_messages`)로 정비

---

## 2. Ubuntu 실행 기준 메모

- 경로 하드코딩 시 Windows 전용 역슬래시(`\\`) 사용 금지
- `.env` 환경변수 기반으로 설정 주입
- 운영 실행은 `flask run`보다 **gunicorn** 같은 WSGI 서버 사용 권장
- PostgreSQL 연결 문자열은 `DATABASE_URL`로 관리
- 파일 인코딩은 UTF-8 기준

---

## 3. 로컬 실행

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

기본 개발 실행도 외부 접속 확인을 위해 `0.0.0.0:5000` 바인딩으로 동작합니다.

- 로컬 접속: `http://127.0.0.1:5000`
- 같은 네트워크/서버 공인 IP 접속: `http://서버IP:5000`
- 도메인 연결 후: `https://kids.forie.kr` 또는 `http://kids.forie.kr`

> `app.py`는 직접 실행용 엔트리포인트이고, `run.py`는 앱 팩토리 기반 실행용 보조 엔트리포인트로 사용할 수 있습니다.

---

## 4. Ubuntu 배포 메모

실서버에서는 아래처럼 Ubuntu 기준으로 실행하는 것을 권장합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env 값 수정
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

> 현재 `requirements.txt`에는 개발용 기준 패키지가 포함되어 있으므로, Ubuntu 운영 배포 시에는 필요하면 `gunicorn`을 추가 설치하세요.

---

## 5. 핵심 운영 흐름

### 5.1 예약 신청 흐름

1. 사용자가 월을 선택하고 신청서를 작성합니다.
2. 신청이 정상 처리되면 예약이 생성됩니다.
3. 이용금액이 0원보다 크면 기본 상태는 `PENDING_PAYMENT`입니다.
4. 이용금액이 `0원`인 월은 자동으로 `PAYMENT_CONFIRMED` 처리됩니다.
5. 신청 완료 후 사용자에게 아래 정보가 모달로 안내됩니다.
   - 신청 월
   - 신청자 정보
   - 이용금액
   - 입금 계좌정보

### 5.2 문의사항 흐름

v2.0부터 기존 `payment_request` 개념을 **문의사항(inquiry)** 흐름으로 정리했습니다.

- 사용자는 문의사항을 등록할 수 있습니다.
- 같은 화면에서 답변 조회가 가능합니다.
- 관리자는 문의 스레드를 보고 답변/수정/삭제할 수 있습니다.

### 5.3 입금확인 흐름

- 은행 연동을 통해 거래를 수집합니다.
- 자동 매칭은 금액 / 입금자명 / 예약 이후 입금 여부 등을 기준으로 수행합니다.
- v2.0에서는 **입금(deposit) 거래만 저장**하고, **30,000원 이하 거래만 적재**하도록 정책이 정리되었습니다.

---

## 6. Supabase 연동 방법

이 프로젝트는 **Supabase REST API 방식**으로 연동합니다.

### 6.1 Supabase에서 확인할 값

Supabase 프로젝트에서 아래 경로로 이동하세요.

- **Project Settings**
- **API**

확인할 값:

- **Project URL**
- **Publishable key**
- **service_role / secret key**

예시:

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=sb_publishable_xxxxx
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

### 6.2 `.env` 파일에 넣을 값

프로젝트 루트에 `.env` 파일을 만들고 아래 값을 설정하세요.

```env
FLASK_SECRET_KEY=아무렇게나길고복잡한문자열
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=sb_publishable_xxxxx
SUPABASE_SERVICE_ROLE_KEY=eyJ...

ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=생성된해시문자열
ADMIN_SESSION_TIMEOUT_MINUTES=30
ADMIN_MAX_LOGIN_ATTEMPTS=5
ADMIN_LOGIN_BLOCK_MINUTES=15

SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_SECURE=true
ENFORCE_SECURE_CONFIG=true
AUTO_ENSURE_NEXT_MONTH_ON_REQUESTS=false

BANK_API_KEY=
BANK_API_SECRET_KEY=
BANK_API_BASE_URL=https://api.bankapi.co.kr

BANK_DEFAULT_CODE=NH
BANK_DEFAULT_ACCOUNT_HOLDER_NAME=
BANK_DEFAULT_ACCOUNT_NUMBER=
BANK_DEFAULT_PAYMENT_AMOUNT=5000

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

관리자 비밀번호는 평문 `ADMIN_PASSWORD`보다 **`ADMIN_PASSWORD_HASH` 사용을 권장**합니다.

해시 생성 예시:

```bash
flask --app app generate-admin-password-hash
```

### 6.3 환경변수 설명

- `BANK_DEFAULT_CODE`: 기본 은행 코드
- `BANK_DEFAULT_ACCOUNT_HOLDER_NAME`: 기본 예금주명
- `BANK_DEFAULT_ACCOUNT_NUMBER`: 기본 계좌번호
- `BANK_DEFAULT_PAYMENT_AMOUNT`: 기본 이용금액

위 값들은 은행 설정 조회 실패 또는 초기 상태에서 **안내용 fallback 정보**로 사용될 수 있습니다.

### 6.4 주의할 점

- `SUPABASE_SERVICE_ROLE_KEY`는 서버에서만 사용하세요.
- service role key는 외부 노출 금지입니다.
- 입주민 공개 기능은 서버를 통해 호출하는 구조를 권장합니다.

### 6.5 연결 테스트 방법

`.env` 입력 후 아래 순서로 확인할 수 있습니다.

```bash
pip install -r requirements.txt
curl -i "https://YOUR_PROJECT.supabase.co/rest/v1/" \
  -H "apikey: YOUR_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY"
```

`200 OK`가 오면 API 접근은 정상입니다.

---

## 7. Supabase 스키마 및 마이그레이션

### 7.1 신규 설치

Supabase SQL Editor에서 루트의 `supabase_schema.sql` 내용을 실행하세요.

이 테이블들이 있어야 현재 Flask 앱이 API 방식으로 동작합니다.

주요 상태값:

- `PENDING_PAYMENT`: 예약대기
- `PAYMENT_CONFIRMED`: 예약완료
- `CANCELLED`: 취소

예약은 월 단위 신청 기준이며, 한 번 신청 후 입금이 확인되면 해당 월 자유 이용 방식입니다.

예약월 상태는 날짜 기준으로 자동 표시됩니다.

- 오픈일 이전: `예약대기`
- 오픈일 ~ 마감일: `예약중`
- 마감일 이후: `예약완료`

### 7.2 v1.5 → v2.0 업그레이드 시 확인사항

기존 데이터를 유지한 채 업그레이드하는 경우 아래 항목을 확인하세요.

- `supabase_schema.sql` 반영
- `scripts/rename_inquiries.sql` 실행 여부 검토
- `scripts/fix_create_reservation_atomic.sql` 실행 여부 검토

특히 v2.0에서는 아래 명칭으로 구조가 정리되었습니다.

- `deposit_requests` → `inquiries`
- `deposit_request_messages` → `inquiry_messages`

### 7.3 운영용 보조 스크립트

상황에 따라 아래 스크립트를 사용할 수 있습니다.

- `scripts/rename_inquiries.sql`
- `scripts/fix_create_reservation_atomic.sql`
- `scripts/hard_reset_recreate_db.sql`
- `scripts/reset_all_data.sql`

> 주의: `hard_reset_recreate_db.sql`, `reset_all_data.sql`은 데이터에 직접 영향을 줄 수 있으므로 운영 DB에서는 반드시 백업 후 사용하세요.

---

## 8. 기본 관리자 계정

- ID: `.env`의 `ADMIN_USERNAME`
- PW: `.env`의 `ADMIN_PASSWORD_HASH`에 대응되는 원본 비밀번호

> 레거시 호환을 위해 `ADMIN_PASSWORD` fallback 이 남아 있지만, 운영에서는 사용하지 않는 것을 권장합니다.

---

## 9. 운영용 CLI 명령

```bash
flask --app app cleanup-expired-data
flask --app app sync-bank-transactions --force
flask --app app ensure-next-month-reservation
flask --app app generate-admin-password-hash
```

### 주요 CLI 설명

- `cleanup-expired-data`: 개인정보 보관기간이 지난 데이터 정리
- `sync-bank-transactions --force`: 은행 거래 즉시 동기화
- `ensure-next-month-reservation`: 다음달 예약 월 자동 생성 보조 실행
- `generate-admin-password-hash`: 관리자 비밀번호 해시 생성

---

## 10. v2.0 운영 체크포인트

- 문의사항 메뉴가 정상 동작하는지 확인
- 관리자 문의사항 관리에서 답변/수정/삭제가 되는지 확인
- 예약 월 생성/수정 시 월별 이용금액이 정상 저장되는지 확인
- 0원 월 신청 시 자동 예약완료가 되는지 확인
- 신청 완료 모달에 계좌정보와 복사 버튼이 노출되는지 확인
- 자동 입금 수집이 입금 거래만 적재하는지 확인
- `inquiries / inquiry_messages` 기준 개인정보 정리 로직이 정상 동작하는지 확인

---

## 11. 운영 보안 권장값

- `SESSION_COOKIE_SECURE=true` (HTTPS 운영 시 필수)
- `SESSION_COOKIE_SAMESITE=Lax`
- `ENFORCE_SECURE_CONFIG=true`
- `ADMIN_PASSWORD_HASH` 사용
- `FLASK_DEBUG=false`

---

## 12. 참고 문서

- 릴리즈 노트: `forie_kdis_releasenote.md`
- 배포 가이드: `DEPLOY_UBUNTU.md`
- 스키마: `supabase_schema.sql`
