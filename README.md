# 게임 개발자 채용공고 디스코드 봇

게임잡·원티드·사람인·잡코리아에서 **기획 / 모델링 / 서버 / 클라이언트** 공고를 모아
매일 **오전 6시(KST)** 에 디스코드 채널로 보냅니다.

기본 설정은 **인턴 · 신입 지원가능 공고만** 모읍니다 — 신입 / 경력무관 / 인턴 / 요구경력 3년 이하.
경력 공고(4년 이상)는 아예 받아오지 않습니다. `config.yaml` 의 `only_entry` 를 `false` 로 하면
경력 공고도 함께 받고, 직군마다 신입/경력 두 갈래로 나뉘어 표시됩니다.

이미 보낸 공고는 SQLite에 기억해 두고, 매일 **새로 올라온 것만** 보냅니다.

---

## 1. 설치

```bash
pip install -r requirements.txt
```

> 윈도우에는 시간대 데이터베이스가 없어서 `tzdata` 가 함께 설치됩니다.
> 이게 없으면 `Asia/Seoul` 을 못 찾아 봇이 시작되지 않습니다.

## 2. 설정 (권장: 자동 도우미)

```bash
python setup.py
```

토큰과 채널 ID만 붙여넣으면 `.env` 를 만들고, **실제로 디스코드에 접속해서**
토큰이 맞는지 · 채널이 보이는지 · 글 쓸 권한이 있는지까지 확인한 뒤
테스트 메시지를 보내줍니다. 하나라도 틀리면 뭐가 틀렸는지 알려주고 `.env` 를 만들지 않습니다.

도우미가 안내하는 값 두 개를 어디서 얻는지:

**봇 토큰** — https://discord.com/developers/applications
→ New Application → 왼쪽 **Bot** → **Reset Token** → 복사

**서버 초대** — 왼쪽 **OAuth2 → URL Generator**
- SCOPES: `bot`, `applications.commands`  ← `applications.commands` 빠지면 슬래시 명령이 안 보입니다
- BOT PERMISSIONS: `Send Messages`, `Embed Links`
- 생성된 URL로 접속 → 내 서버 선택 → 승인

**채널 ID** — 디스코드 **설정 → 고급 → 개발자 모드** 켜고
공고 받을 채널 **우클릭 → 채널 ID 복사**

### 수동으로 하려면

`.env.example` 을 `.env` 로 복사하고 직접 채워도 됩니다.

```
DISCORD_TOKEN=봇_토큰
DISCORD_CHANNEL_ID=채널_ID
```

## 3. 실행

```bash
python bot.py
```

봇을 처음 켜면 기존 공고 수백 건을 한꺼번에 쏟아내지 않고 **조용히 DB에만 저장**합니다
(`config.yaml` 의 `seed_on_first_run`). 다음 날 오전 6시부터 새 공고만 올라옵니다.

바로 결과를 보고 싶으면 채널에서 `/수집` 을 치세요.

---

## 슬래시 명령

| 명령 | 하는 일 |
|---|---|
| `/공고 [직군] [구분] [개수]` | 저장된 공고를 직군·경력별로 조회 |
| `/수집` | 지금 즉시 수집해서 새 공고를 이 채널에 발송 |
| `/현황` | 직군별·경력별 누적 수집 통계 |

## 디스코드 없이 점검하기

```bash
python dryrun.py                    # 전체 소스 수집만 (DB 저장 안 함)
python dryrun.py --source gamejob   # 특정 소스만
python dryrun.py --save             # DB 저장까지
```

수집 건수, 직군별 분포, 임베드가 디스코드 글자수 제한을 넘지 않는지까지 찍어줍니다.

---

## 설정 (`config.yaml`)

```yaml
schedule:
  hour: 6              # 발송 시각
  minute: 0
  timezone: Asia/Seoul
  seed_on_first_run: true

sources:
  gamejob:  true       # 메인
  wanted:   true
  saramin:  true
  jobkorea: true       # 넷 중 가장 깨지기 쉬움

entry_max_years: 3     # 이 연차 이하를 '신입 지원가능'으로 분류
only_entry: true       # true 면 경력 공고를 아예 버림
request_delay: 0.7     # 요청 간 대기(초). 낮추면 차단 위험
max_per_section: 25    # 직군·구분당 최대 표시 수
```

---

## 소스별 특성과 한계

| 소스 | 방식 | 수집량 | 비고 |
|---|---|---|---|
| **게임잡** | 직무 코드 필터 + 페이지네이션 | 약 1,000건 | **메인.** 게임 전용 사이트라 직군 분류가 정확하고 전체 공고를 다 가져옵니다 |
| **원티드** | 공식 JSON API (`job_group_id=959`) | 최신 50건 | 연차가 숫자로 와서 경력 분류가 가장 정확. 단, **서버가 50건에서 자릅니다** (`offset`·`sort`·카테고리 필터를 넘겨도 무시함). 매일 신규분만 뽑는 용도라 실사용엔 지장 없음 |
| **사람인** | 키워드 검색 + HTML 파싱 | 약 150건 | 게임 전용 직무 트리가 없어 키워드로 찾은 뒤 `jobbot/relevance.py` 로 걸러냅니다 |
| **잡코리아** | 키워드 검색 + HTML 파싱 | 약 160건 | React 렌더링이라 **가장 깨지기 쉬움**. 카드 경계(`data-sentry-component="CardJob"`)와 링크 앵커에 의존합니다 |

### 직군 매핑

게임잡 직무 코드 → 직군

| 직군 | 게임잡 코드 |
|---|---|
| 기획 | 9 (게임기획) |
| 모델링 | 6 (모델링) |
| 서버 | 16 (서버) |
| 클라이언트 | 1 (게임개발-클라이언트), 2 (게임개발-모바일) |

`jobbot/sources/gamejob.py` 의 `DUTY_CODES` 에서 바꿀 수 있습니다.
예를 들어 모델링에 원화(5)·애니메이션(7)·이펙트(8)를 더하고 싶으면
`"모델링": ["6", "5", "7", "8"]` 로 고치면 됩니다.

원티드는 `TAG_TO_CATEGORY`, 사람인·잡코리아는 각 파일의 `KEYWORDS` 입니다.

### 경력 분류 규칙

`jobbot/classify.py`

`only_entry: true` 면 아래 판정에서 '경력'으로 나온 공고를 버립니다.
게임잡은 서버 필터(`career_stat=0,2` + `career=1_3`)까지 걸어서 애초에 받아오지도 않습니다.

- `신입`, `경력무관`, 고용형태가 `인턴` → 신입 트랙
- `경력N년↑`, `N~M년` → N ≤ 3 이면 신입 트랙, 아니면 경력
- 경력 표기를 못 읽은 공고는 제목에 신입/주니어/인턴이 있을 때만 신입 트랙

> `경력무관` 공고가 상당히 많아 신입 목록이 길어집니다. 목록은
> **신입 → 경력무관 → 경력1~3년** 순으로 정렬되고 각 줄에 원문 경력 표기가 붙으니
> 실제 신입 공고를 위에서 바로 확인할 수 있습니다.

---

## PC를 꺼둬도 되게 하기 (GitHub Actions)

`bot.py` 는 켜져 있어야 동작합니다. PC와 무관하게 매일 6시에 받으려면
GitHub Actions 에 올리세요. **무료이고 카드 등록도 필요 없습니다.**

동작 방식이 다릅니다.

| | `bot.py` (로컬) | GitHub Actions |
|---|---|---|
| 실행 | 계속 떠 있음 | 하루 한 번 실행하고 종료 |
| 매일 발송 | ○ | ○ |
| 슬래시 명령 | ○ | **✗** (상시 접속이 아니라 불가) |
| PC 꺼도 됨 | ✗ | ○ |

### 1) 저장소 만들기

이 폴더를 GitHub 에 올립니다. **비공개(Private)로 만드세요.**

```bash
git init
git add .
git commit -m "게임 채용공고 봇"
git branch -M main
git remote add origin https://github.com/<내계정>/<저장소이름>.git
git push -u origin main
```

`.env` 는 `.gitignore` 에 있어서 올라가지 않습니다. 토큰은 다음 단계에서 따로 넣습니다.

### 2) 토큰을 Secrets 에 등록

저장소 → **Settings** → 왼쪽 **Secrets and variables** → **Actions**
→ **New repository secret** 로 두 개 등록합니다.

| Name | Secret |
|---|---|
| `DISCORD_TOKEN` | 봇 토큰 |
| `DISCORD_CHANNEL_ID` | 채널 ID |

`.env` 파일에 있는 값 그대로입니다.

### 3) 실행해 보기

저장소 → **Actions** 탭 → 왼쪽 **채용공고 발송** → 오른쪽 **Run workflow**

첫 실행은 기존 공고를 기준선으로 저장하고 맛보기 몇 건만 보냅니다.
그 다음부터 매일 오전 6시에 신규분만 올라옵니다.

> GitHub Actions 의 예약 실행은 서버가 붐비면 **10~30분 늦어질 수 있습니다.**
> 6시 정각을 보장하지는 않습니다.

> 60일 동안 저장소에 아무 커밋도 없으면 GitHub 가 예약 실행을 자동으로 멈춥니다.
> 이 워크플로는 매일 `data/seen.txt` 를 커밋하므로 그럴 일은 없습니다.

### 로컬에서 한 번만 돌려보기

```bash
python run_once.py --dry-run   # 발송 안 하고 콘솔에만 출력
python run_once.py             # 실제 발송
```

## 문제가 생기면

- **봇이 `시간대 'Asia/Seoul' 를 찾을 수 없습니다` 로 종료** → `pip install tzdata`
- **슬래시 명령이 안 보임** → 초대 URL에 `applications.commands` 스코프가 있었는지 확인.
  등록에 최대 1시간 걸릴 수 있습니다.
- **특정 사이트만 0건** → 그 사이트가 마크업을 바꾼 것입니다.
  `config.yaml` 에서 해당 소스를 `false` 로 꺼도 나머지는 정상 동작합니다.
  (한 소스가 예외를 내도 다른 소스는 계속 수집합니다)
- **수집이 오래 걸림** → 4개 소스 전체는 3~4분 걸립니다. `request_delay` 를 낮추면
  빨라지지만 차단당할 수 있습니다.

## 파일 구조

```
setup.py                  최초 설정 도우미 (.env 생성 + 접속 확인)
bot.py                    상시 실행 봇 · 스케줄러 · 슬래시 명령
run_once.py               한 번 실행하고 끝 (GitHub Actions 용)
.github/workflows/daily.yml   매일 오전 6시 자동 실행
dryrun.py                 디스코드 없이 수집 파이프라인 점검
config.yaml               설정
jobbot/
  models.py               Posting 자료구조, 직군 상수
  classify.py             경력 표기 → 신입/경력 분류
  relevance.py            키워드 검색 소스용 관련성 필터
  collector.py            소스 병렬 수집
  store.py                중복 제거 (SQLite / seen.txt 두 가지)
  digest.py               디스코드 임베드 조립
test_classify.py          분류·필터 로직 테스트 (네트워크 불필요)
  sources/
    gamejob.py  wanted.py  saramin.py  jobkorea.py
```
