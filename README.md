# 아파트 어린이 놀이터 월별 예약 관리 시스템

Flask + SQLAlchemy + Jinja2 기반 MVP입니다. 개발은 Windows에서 해도 되지만, **실제 실행환경은 Ubuntu**를 기준으로 구성합니다.

## Ubuntu 실행 기준 메모

- 경로 하드코딩 시 Windows 전용 역슬래시(`\\`) 사용 금지
- `.env` 환경변수 기반으로 설정 주입
- 운영 실행은 `flask run`보다 **gunicorn** 같은 WSGI 서버 사용 권장
- PostgreSQL 연결 문자열은 `DATABASE_URL`로 관리
- 파일 인코딩은 UTF-8 기준

## 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Windows PowerShell에서는 가상환경 활성화 명령만 다르며, 앱 구조 자체는 Ubuntu 배포를 기준으로 유지합니다.

### Windows PowerShell 예시

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

## Ubuntu 배포 메모

실서버에서는 아래처럼 Ubuntu 기준으로 실행하는 것을 권장합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env 값 수정
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

> 현재 `requirements.txt`에는 개발용 MVP 기준 패키지만 넣어두었으므로, Ubuntu 운영 배포 시에는 `gunicorn`을 추가 설치하면 됩니다.

## Supabase 연동 방법

이 프로젝트는 현재 **Supabase REST API 방식**으로 연동하는 기준입니다.

### 1) Supabase에서 확인할 값

Supabase 프로젝트에서 아래 순서로 들어가세요.

- **Project Settings**
- **API**

여기서 아래 값을 확인합니다.

- **Project URL**
- **Publishable key**
- **service_role / secret key**

예시:

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=sb_publishable_xxxxx
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

### 2) `.env` 파일에 넣을 값

프로젝트 루트에 `.env` 파일을 만들고 아래처럼 넣으면 됩니다.

```env
FLASK_SECRET_KEY=아무렇게나길고복잡한문자열
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=sb_publishable_xxxxx
SUPABASE_SERVICE_ROLE_KEY=eyJ...
ADMIN_USERNAME=admin
ADMIN_PASSWORD=원하는관리자비밀번호
```

### 3) 주의할 점

- `SUPABASE_SERVICE_ROLE_KEY`는 서버에서만 사용하세요.
- service role key는 외부 노출 금지입니다.
- 입주민 공개 기능은 서버를 통해 호출하는 구조를 권장합니다.

### 4) 연결 테스트 방법

`.env` 입력 후 아래 순서로 확인하면 됩니다.

```bash
pip install -r requirements.txt
curl -i "https://YOUR_PROJECT.supabase.co/rest/v1/" \
  -H "apikey: YOUR_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY"
```

`200 OK`가 오면 API 접근은 정상입니다.

### 5) 내가 확인해줄 수 있는 값

당신이 `.env`에 넣기 전에 아래 둘 중 하나를 알려주면, 형식이 맞는지 바로 확인해드릴 수 있습니다.

- Supabase의 **Project URL**
- 또는 key 앞뒤 일부만 가린 값

## Supabase 스키마 생성

Supabase SQL Editor에서 루트의 `supabase_schema.sql` 내용을 실행하세요.
이 테이블들이 있어야 현재 Flask 앱이 API 방식으로 동작합니다.

추가 기능 확장 시에는 아래 상태값 기준으로 운영합니다.

- `PENDING_PAYMENT`: 예약대기
- `PAYMENT_CONFIRMED`: 예약완료
- `CANCELLED`: 취소

예약은 월 단위 신청 기준이며, 한 번 신청 후 입금이 확인되면 해당 월 자유 이용 방식입니다.

예약월 상태는 별도 수동 변경이 아니라 날짜 기준으로 자동 표시됩니다.

- 오픈일 이전: `예약대기`
- 오픈일 ~ 마감일: `예약중`
- 마감일 이후: `예약완료`

> 참고: Supabase 테이블을 예전에 먼저 생성했다면, `payment_confirmed_at` 같은 신규 컬럼은 SQL Editor에서 `ALTER TABLE`로 추가해야 할 수 있습니다.

현재 앱은 호환성을 위해 `payment_confirmed_at` 컬럼이 아직 없어도 `settings.policy_json`에 보조 저장하여 입금확인일을 표시하도록 처리되어 있습니다.

## 기본 관리자 계정

- ID: `.env`의 `ADMIN_USERNAME`
- PW: `.env`의 `ADMIN_PASSWORD`

최초 실행 시 관리자 계정과 기본 설정 레코드가 자동 생성됩니다.