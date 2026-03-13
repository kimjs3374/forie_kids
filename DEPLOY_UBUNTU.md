# Ubuntu 배포 절차 (`kids.forie.kr`)

이 문서는 현재 프로젝트를 **Ubuntu 서버 + Nginx + Gunicorn** 조합으로 배포하는 절차입니다.

실행 기준:
- 개발환경: Windows
- 실제 운영환경: Ubuntu
- 앱 구조: Flask + Supabase REST API
- 목표 도메인: `kids.forie.kr`

---

## 1. 사전 준비

필요한 것:

- Ubuntu 서버 1대
- `kids.forie.kr` DNS 수정 권한
- 서버에 80 / 443 포트 허용
- Git 또는 파일 업로드 수단
- Supabase 프로젝트

`.env`에 필요한 값:

```env
FLASK_SECRET_KEY=change-this-secret
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR_PUBLISHABLE_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
ADMIN_USERNAME=forie
ADMIN_PASSWORD=change-this-password
```

---

## 2. Ubuntu 패키지 설치

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx git
```

---

## 3. 프로젝트 배치

권장 위치:

```bash
sudo mkdir -p /var/www/kids
sudo chown $USER:$USER /var/www/kids
cd /var/www/kids
```

### 방법 A: git으로 가져오기

```bash
git clone <YOUR_REPOSITORY_URL> .
```

### 방법 B: 로컬 파일 업로드

Windows에서 프로젝트 전체를 서버의 `/var/www/kids`로 업로드합니다.

업로드 시 제외 권장:
- `.venv/`
- `__pycache__/`
- `.git/`

---

## 4. 가상환경 생성 및 의존성 설치

```bash
cd /var/www/kids
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

---

## 5. 환경변수 파일 생성

```bash
cd /var/www/kids
cp .env.example .env
nano .env
```

`.env`에 실제 운영값 입력:

```env
FLASK_SECRET_KEY=실제_시크릿값
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR_PUBLISHABLE_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
ADMIN_USERNAME=forie
ADMIN_PASSWORD=강한비밀번호
```

---

## 6. Supabase 스키마 생성

Supabase SQL Editor에서 프로젝트 루트의 `supabase_schema.sql` 내용을 실행합니다.

필수 테이블:
- `settings`
- `reservation_months`
- `reservation_slots`
- `reservations`

---

## 7. Gunicorn 수동 실행 테스트

먼저 앱이 서버에서 정상 실행되는지 확인합니다.

```bash
cd /var/www/kids
source .venv/bin/activate
gunicorn -w 2 -b 127.0.0.1:8000 app:app
```

정상이면 Gunicorn이 8000 포트에서 떠 있어야 합니다.

다른 SSH 세션에서 확인:

```bash
curl http://127.0.0.1:8000
```

응답이 오면 `Ctrl+C`로 종료하고 systemd 등록으로 넘어갑니다.

---

## 8. systemd 서비스 등록

파일 생성:

```bash
sudo nano /etc/systemd/system/kids.service
```

내용:

```ini
[Unit]
Description=Kids Flask App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/kids
EnvironmentFile=/var/www/kids/.env
ExecStart=/var/www/kids/.venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

권한 정리:

```bash
sudo chown -R www-data:www-data /var/www/kids
sudo systemctl daemon-reload
sudo systemctl enable kids
sudo systemctl start kids
sudo systemctl status kids
```

로그 확인:

```bash
sudo journalctl -u kids -f
```

---

## 9. Nginx 설정

파일 생성:

```bash
sudo nano /etc/nginx/sites-available/kids.forie.kr
```

내용:

```nginx
server {
    listen 80;
    server_name kids.forie.kr;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

활성화:

```bash
sudo ln -s /etc/nginx/sites-available/kids.forie.kr /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 10. DNS 연결

DNS 관리 화면에서 아래 레코드 추가:

- 타입: `A`
- 이름: `kids`
- 값: `서버 공인 IP`

즉, `kids.forie.kr`가 Ubuntu 서버 IP를 가리키게 해야 합니다.

확인:

```bash
nslookup kids.forie.kr
```

---

## 11. HTTPS 설정

DNS 반영 후 SSL 적용:

```bash
sudo certbot --nginx -d kids.forie.kr
```

자동 갱신 확인:

```bash
sudo systemctl status certbot.timer
```

---

## 12. 운영 확인

확인 항목:

1. `https://kids.forie.kr` 접속
2. 메인 페이지 로드 확인
3. `/admin` 로그인 확인
4. 공지 저장 확인
5. 예약 월 생성 확인
6. 슬롯 생성 확인
7. 예약 등록 확인

## 12-1. 0.0.0.0 바인딩 관련 메모

개발 서버 기준으로는 Flask가 `0.0.0.0:5000` 에 바인딩되도록 설정되어 있습니다.

- 즉 서버 방화벽만 열려 있으면 외부에서 `서버IP:5000` 직접 접근 가능
- 운영 환경에서는 직접 5000 포트 노출보다 **Nginx → Gunicorn 프록시 방식**을 권장
- 실제 서비스 접속 주소는 `kids.forie.kr` 로 두고, 5000 포트는 내부 확인용으로만 쓰는 것이 안전합니다.

---

## 13. 장애 점검 포인트

### 앱이 안 뜰 때

```bash
sudo systemctl status kids
sudo journalctl -u kids -n 100 --no-pager
```

### Nginx 오류일 때

```bash
sudo nginx -t
sudo systemctl status nginx
```

### 도메인 연결 확인

```bash
nslookup kids.forie.kr
curl -I http://kids.forie.kr
curl -I https://kids.forie.kr
```

---

## 14. 배포 후 수정 배포 방법

코드 변경 후:

```bash
cd /var/www/kids
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart kids
```

---

## 15. 중요 메모

- `SUPABASE_SERVICE_ROLE_KEY`는 절대 브라우저에 노출하면 안 됩니다.
- 운영환경에서는 Flask 개발 서버가 아니라 반드시 Gunicorn 사용
- Ubuntu 기준 경로/권한으로 유지
- 필요하면 추후 `www-data` 대신 전용 배포 계정으로 분리 가능
