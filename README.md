# 제품 소개서 다국어 변환 (예제3)

한국어 제품 스펙·소개를 **OpenAI API**를 사용해  
영어 / 중국어(간체) / 스페인어(LATAM) **B2B 바이어용 비즈니스 어투**로 현지화하고  
결과를 **HTML 테이블**로 출력하는 예제 프로젝트입니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| CSV 자동 인코딩 감지 | CP949 / UTF-8 자동 폴백 지원 |
| B2B 현지화 번역 | 단순 직역이 아닌 바이어용 카탈로그 어투 |
| 3개 언어 동시 출력 | 영어 · 중국어 · 스페인어 |
| HTML 결과 파일 생성 | 브라우저에서 즉시 확인 가능 |
| 번역 행 수 조절 | MAX_TRANSLATE_ROWS 환경변수로 제어 |

---

## 프로젝트 구조

```
example2/
├── 예제3.CSV                  # 원본 한국어 제품 데이터 (500행)
├── translate_products.py      # 메인 번역·HTML 생성 스크립트
├── requirements.txt           # 의존성
├── .env.example               # 환경변수 설정 예시
├── .gitignore
└── README.md
```

---

## 설치 방법

```bash
pip install -r requirements.txt
```

**Python 3.9 이상** 필요

---

## 환경변수 설정

`.env.example`을 복사해 `.env` 파일을 생성하고 API 키를 입력합니다.

```bash
cp .env.example .env
```

`.env` 파일:

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
MAX_TRANSLATE_ROWS=20
```

- `OPENAI_API_KEY` : OpenAI API 키 (필수)
- `MAX_TRANSLATE_ROWS` : 번역할 최대 행 수 (기본값 20, 전체 번역 시 500으로 설정)

> `.env` 파일은 `.gitignore`에 의해 Git에 커밋되지 않습니다.

---

## 실행 방법

```bash
python translate_products.py
```

실행 완료 후 `translated_products.html` 파일이 생성됩니다.  
브라우저로 열면 아래 컬럼이 포함된 테이블을 확인할 수 있습니다.

| 컬럼 | 내용 |
|------|------|
| No / 품목코드 / 제품명 | 원본 제품 정보 |
| 카테고리 / 주요 스펙 / 타겟 시장 | 원본 스펙 정보 |
| 한국어 소개 | 원문 |
| 영어 (English) | B2B 현지화 번역 |
| 중국어 (简体中文) | B2B 현지화 번역 |
| 스페인어 (Español LATAM) | B2B 현지화 번역 |

---

## 사용 모델

- `gpt-4.1-mini` (OpenAI Chat Completions)
- JSON 응답 모드(`response_format: json_object`) 사용

---

## 라이선스

MIT
