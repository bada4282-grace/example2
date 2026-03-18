import csv
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List

from openai import OpenAI

# ────────────────────────────────────────────────────────────────
# 지원 언어 정의
# ────────────────────────────────────────────────────────────────
LANG_MAP: Dict[str, Dict[str, str]] = {
    "영어":   {"key": "english",  "label": "영어 (English)",          "color": "#3b82f6", "dir": "ltr"},
    "중국어": {"key": "chinese",  "label": "중국어 (简体中文)",        "color": "#ef4444", "dir": "ltr"},
    "스페인어":{"key": "spanish", "label": "스페인어 (Español LATAM)", "color": "#f59e0b", "dir": "ltr"},
    "일어":   {"key": "japanese", "label": "일어 (日本語)",            "color": "#10b981", "dir": "ltr"},
    "아랍어": {"key": "arabic",   "label": "아랍어 (العربية)",         "color": "#8b5cf6", "dir": "rtl"},
    "프랑스어":{"key": "french",  "label": "프랑스어 (Français)",      "color": "#ec4899", "dir": "ltr"},
    "독일어": {"key": "german",   "label": "독일어 (Deutsch)",         "color": "#6366f1", "dir": "ltr"},
}

# 테이블에 표시할 언어 순서
LANG_ORDER = ["영어", "중국어", "스페인어", "일어", "아랍어", "프랑스어", "독일어"]

# 캐시 파일 경로
CACHE_FILE = os.path.join(os.path.dirname(__file__), "translations_cache.json")


# ────────────────────────────────────────────────────────────────
# 데이터 모델
# ────────────────────────────────────────────────────────────────
@dataclass
class ProductIntro:
    """제품 정보 및 번역 결과를 보관하기 위한 데이터 구조."""

    no: str
    code: str
    name: str
    category: str
    spec: str
    target_market: str
    kor_intro: str
    target_langs: List[str]          # CSV의 번역필요언어 파싱 결과 (예: ["영어", "중국어"])
    translations: Dict[str, str] = field(default_factory=dict)  # {lang_key: translated_text}


# ────────────────────────────────────────────────────────────────
# 환경 변수 / OpenAI 클라이언트
# ────────────────────────────────────────────────────────────────
def load_env() -> None:
    """현재 디렉터리의 .env 파일에서 환경변수를 로드한다."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


def build_client() -> OpenAI:
    """OpenAI 클라이언트를 생성한다."""
    load_env()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
    return OpenAI(api_key=api_key)


# ────────────────────────────────────────────────────────────────
# CSV 읽기
# ────────────────────────────────────────────────────────────────
def parse_target_langs(raw: str) -> List[str]:
    """'영어+중국어+일어' 형식의 문자열을 파싱해 언어 목록을 반환한다."""
    if not raw:
        return []
    langs = [tok.strip() for tok in raw.replace("，", "+").split("+")]
    return [lang for lang in langs if lang in LANG_MAP]


def read_products(csv_path: str) -> List[ProductIntro]:
    """CSV 파일에서 제품 정보를 읽어온다.

    CP949(EUC-KR) → UTF-8-SIG → UTF-8 순으로 인코딩 폴백한다.
    첫 번째 행은 파일 제목 행이므로 건너뜀.
    """
    products: List[ProductIntro] = []
    last_error: Exception | None = None

    for encoding in ("cp949", "utf-8-sig", "utf-8"):
        try:
            with open(csv_path, "r", encoding=encoding, newline="") as f:
                next(f)  # 1행: 파일 제목 행 건너뜀
                reader = csv.DictReader(f)
                for row in reader:
                    products.append(
                        ProductIntro(
                            no=row.get("No", "").strip(),
                            code=row.get("품목코드", "").strip(),
                            name=row.get("제품명", "").strip(),
                            category=row.get("카테고리", "").strip(),
                            spec=row.get("주요스펙", "").strip(),
                            target_market=row.get("타겟시장", "").strip(),
                            kor_intro=row.get("한국어소개", "").strip(),
                            target_langs=parse_target_langs(row.get("번역필요언어", "")),
                        )
                    )
            return products
        except UnicodeDecodeError as error:
            last_error = error
            products = []
            continue

    raise RuntimeError(
        f"CSV 파일을 읽을 수 없습니다. 인코딩을 확인하세요. 마지막 오류: {last_error}"
    )


# ────────────────────────────────────────────────────────────────
# 번역
# ────────────────────────────────────────────────────────────────
def translate_intro(
    client: OpenAI,
    text: str,
    target_langs: List[str],
) -> Dict[str, str]:
    """한국어 제품 소개를 지정된 언어들로 B2B 현지화 번역한다.

    Returns:
        {lang_key: translated_text} 딕셔너리
    """
    if not target_langs:
        return {}

    # 번역 대상 언어 설명 목록 생성
    lang_descriptions = {
        "영어":    "English — for US/EU industrial B2B buyers",
        "중국어":  "Simplified Chinese (简体中文) — for Mainland China B2B buyers",
        "스페인어":"Latin American Spanish (Español) — for B2B buyers in Mexico, Brazil, Argentina",
        "일어":    "Japanese (日本語) — for Japanese B2B buyers",
        "아랍어":  "Arabic (العربية) — for Middle East/Gulf B2B buyers",
        "프랑스어":"French (Français) — for France, Belgium, and Francophone Africa B2B buyers",
        "독일어":  "German (Deutsch) — for Germany, Austria, Switzerland B2B buyers",
    }

    lang_lines = "\n".join(
        f'  - "{LANG_MAP[lang]["key"]}": {lang_descriptions[lang]}'
        for lang in target_langs
    )
    json_keys = ", ".join(f'"{LANG_MAP[lang]["key"]}"' for lang in target_langs)

    system_prompt = (
        "You are a senior B2B marketing copywriter and industrial product localization expert. "
        "Localize Korean product descriptions for professional business buyers in each target market. "
        "Use business catalog / procurement proposal tone. "
        "Highlight technical specs and value propositions naturally. "
        "Never invent specs not present in the source text."
    )

    user_prompt = (
        f"Source (Korean):\n{text}\n\n"
        f"Translate and localize into the following languages only:\n{lang_lines}\n\n"
        f"Return a JSON object with ONLY these keys: {json_keys}\n"
        "No other text or explanation."
    )

    last_exc: Exception | None = None
    for attempt in range(1, 3):
        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                timeout=40.0,
            )
            break
        except Exception as exc:
            last_exc = exc
            print(f"    [재시도 {attempt}/2] 오류: {exc}")
    else:
        raise RuntimeError(f"번역 실패 (2회 재시도 초과): {last_exc}")

    content = completion.choices[0].message.content
    if not content:
        raise RuntimeError("번역 결과를 받지 못했습니다.")

    data = json.loads(content)
    return {LANG_MAP[lang]["key"]: data.get(LANG_MAP[lang]["key"], "").strip()
            for lang in target_langs}


# ────────────────────────────────────────────────────────────────
# 캐시
# ────────────────────────────────────────────────────────────────
def load_cache() -> Dict[str, Dict[str, str]]:
    """번역 캐시 로드. {품목코드: {lang_key: text}}"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: Dict[str, Dict[str, str]]) -> None:
    """번역 캐시 저장."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ────────────────────────────────────────────────────────────────
# HTML 생성
# ────────────────────────────────────────────────────────────────
def generate_html(products: List[ProductIntro]) -> str:
    """원문 + 지정 언어별 번역을 모두 보여주는 HTML을 생성한다."""

    # 제품명 필터 옵션
    product_names = sorted(set(p.name for p in products if p.name))
    name_options = "\n".join(
        f'<option value="{n}">{n}</option>' for n in product_names
    )

    # 번역언어 필터 옵션
    lang_options = "\n".join(
        f'<option value="{LANG_MAP[k]["key"]}">{LANG_MAP[k]["label"]}</option>'
        for k in LANG_ORDER
    )

    # 테이블 헤더 (고정 컬럼 + 7개 언어 컬럼)
    lang_headers = "\n".join(
        f'<th class="lang-col" style="border-top:3px solid {LANG_MAP[k]["color"]}" '
        f'data-lang="{LANG_MAP[k]["key"]}">{LANG_MAP[k]["label"]}</th>'
        for k in LANG_ORDER
    )

    # 테이블 행 생성
    rows_html_list: List[str] = []
    for p in products:
        # 이 제품이 필요로 하는 언어 key 집합
        needed_keys = {LANG_MAP[lang]["key"] for lang in p.target_langs if lang in LANG_MAP}
        lang_badge = " ".join(
            f'<span class="badge" style="background:{LANG_MAP[l]["color"]}">{LANG_MAP[l]["label"].split(" ")[0]}</span>'
            for l in p.target_langs if l in LANG_MAP
        )

        # 각 언어 셀 생성
        lang_cells = ""
        for k in LANG_ORDER:
            lang_key = LANG_MAP[k]["key"]
            text = p.translations.get(lang_key, "")
            is_rtl = LANG_MAP[k]["dir"] == "rtl"
            if lang_key in needed_keys:
                rtl_attr = ' dir="rtl" class="rtl-cell"' if is_rtl else ""
                cell_content = text if text else '<span class="pending">번역 대기</span>'
                lang_cells += (
                    f'<td class="lang-cell" data-lang="{lang_key}"{rtl_attr}>'
                    f"{cell_content}</td>"
                )
            else:
                lang_cells += f'<td class="lang-cell na" data-lang="{lang_key}">—</td>'

        rows_html_list.append(
            f'<tr data-name="{p.name}" data-langs="{",".join(needed_keys)}">'
            f"<td>{p.no}</td>"
            f"<td>{p.code}</td>"
            f"<td>{p.name}</td>"
            f"<td>{p.category}</td>"
            f"<td class='spec'>{p.spec}</td>"
            f"<td>{p.target_market}</td>"
            f"<td class='lang-badges'>{lang_badge}</td>"
            f"<td class='kor'>{p.kor_intro}</td>"
            f"{lang_cells}"
            "</tr>"
        )

    body_rows = "\n".join(rows_html_list)
    total = len(products)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>제품 소개 다국어 번역 결과</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
            background: #f0f2f5;
            color: #1f2933;
            padding: 24px;
        }}
        /* ── 헤더 ── */
        .page-header {{ margin-bottom: 20px; }}
        .page-header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
        .page-header p {{ font-size: 13px; color: #6b7280; }}

        /* ── 툴바 ── */
        .toolbar {{
            display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
            background: #fff; border-radius: 8px; padding: 12px 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 14px;
        }}
        .toolbar label {{ font-size: 12px; font-weight: 600; color: #374151; white-space: nowrap; }}
        .toolbar select {{
            padding: 6px 28px 6px 10px; border: 1px solid #d1d5db; border-radius: 6px;
            font-size: 12.5px; background: #f9fafb; color: #111827; cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
            background-repeat: no-repeat; background-position: right 7px center; min-width: 160px;
        }}
        .toolbar select:focus {{ outline: none; border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,.15); }}
        .btn {{
            padding: 6px 14px; border-radius: 6px; border: none;
            font-size: 12.5px; font-weight: 600; cursor: pointer;
        }}
        .btn-primary {{ background: #6366f1; color: #fff; }}
        .btn-primary:hover {{ background: #4f46e5; }}
        .btn-ghost {{ background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }}
        .btn-ghost:hover {{ background: #e5e7eb; }}
        .divider {{ width: 1px; height: 24px; background: #e5e7eb; }}
        .count-info {{ font-size: 12px; color: #6b7280; margin-left: auto; white-space: nowrap; }}
        .count-info strong {{ color: #6366f1; font-size: 14px; }}

        /* ── 테이블 ── */
        .table-wrap {{
            width: 100%; overflow-x: auto; border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }}
        table {{
            width: 100%; border-collapse: collapse; background: #fff;
            min-width: 1400px; font-size: 12.5px;
        }}
        thead {{ background: #111827; color: #f9fafb; position: sticky; top: 0; z-index: 2; }}
        th {{
            padding: 10px 12px; text-align: left; white-space: nowrap;
            font-size: 11.5px; letter-spacing: .03em; font-weight: 600;
        }}
        td {{ padding: 9px 12px; border-bottom: 1px solid #f0f2f5; vertical-align: top; line-height: 1.55; }}
        tbody tr:nth-child(even) {{ background: #fafafa; }}
        tbody tr:hover {{ background: #eef2ff; }}
        tbody tr.hidden {{ display: none; }}

        /* ── 셀 종류 ── */
        td.kor {{ color: #374151; max-width: 200px; }}
        td.spec {{ color: #6b7280; white-space: nowrap; }}
        td.lang-cell {{ max-width: 220px; }}
        td.na {{ color: #d1d5db; text-align: center; }}
        td.rtl-cell {{ text-align: right; direction: rtl; }}
        .pending {{ color: #9ca3af; font-style: italic; font-size: 11px; }}

        /* ── 배지 ── */
        .badge {{
            display: inline-block; padding: 1px 6px; border-radius: 4px;
            color: #fff; font-size: 10.5px; font-weight: 600; margin: 1px 1px 1px 0;
            white-space: nowrap;
        }}
        .lang-badges {{ min-width: 100px; }}

        /* ── 빈 결과 ── */
        .no-result {{
            text-align: center; padding: 48px; color: #9ca3af;
            font-size: 14px; display: none;
        }}
    </style>
</head>
<body>
    <div class="page-header">
        <h1>제품 소개 다국어 번역 결과</h1>
        <p>각 제품의 <strong>번역필요언어</strong> 컬럼 기준으로 B2B 현지화 번역을 제공합니다. (총 {total}개 제품)</p>
    </div>

    <div class="toolbar">
        <label>제품명</label>
        <select id="nameFilter" onchange="applyFilter()">
            <option value="">— 전체 —</option>
            {name_options}
        </select>

        <div class="divider"></div>

        <label>번역 언어</label>
        <select id="langFilter" onchange="applyFilter()">
            <option value="">— 전체 —</option>
            {lang_options}
        </select>

        <button class="btn btn-ghost" onclick="resetFilter()">초기화</button>

        <span class="count-info">
            표시: <strong id="visibleCount">{total}</strong> / {total}개
        </span>
    </div>

    <div class="table-wrap">
        <table id="mainTable">
            <thead>
                <tr>
                    <th>No</th>
                    <th>품목코드</th>
                    <th>제품명</th>
                    <th>카테고리</th>
                    <th>주요 스펙</th>
                    <th>타겟 시장</th>
                    <th>번역 언어</th>
                    <th>한국어 소개</th>
                    {lang_headers}
                </tr>
            </thead>
            <tbody id="tableBody">
                {body_rows}
            </tbody>
        </table>
        <p class="no-result" id="noResult">조건에 맞는 제품이 없습니다.</p>
    </div>

    <script>
        const TOTAL = {total};

        function applyFilter() {{
            const nameVal = document.getElementById('nameFilter').value;
            const langVal = document.getElementById('langFilter').value;
            const rows = document.querySelectorAll('#tableBody tr');
            let visible = 0;

            rows.forEach(row => {{
                const name = row.dataset.name || '';
                const langs = row.dataset.langs || '';
                const matchName = !nameVal || name === nameVal;
                const matchLang = !langVal || langs.split(',').includes(langVal);
                const show = matchName && matchLang;
                row.classList.toggle('hidden', !show);
                if (show) visible++;
            }});

            document.getElementById('visibleCount').textContent = visible;
            document.getElementById('noResult').style.display = visible === 0 ? 'block' : 'none';
        }}

        function resetFilter() {{
            document.getElementById('nameFilter').value = '';
            document.getElementById('langFilter').value = '';
            applyFilter();
        }}
    </script>
</body>
</html>
"""
    return html


# ────────────────────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────────────────────
def main() -> None:
    """CSV를 읽어 번역필요언어 기준으로 번역하고 HTML 결과를 생성한다.

    --html-only: 번역 없이 캐시 데이터로 HTML만 재생성
    """
    html_only = "--html-only" in sys.argv

    csv_path = os.path.join(os.path.dirname(__file__), "예제3.CSV")
    output_html = os.path.join(os.path.dirname(__file__), "translated_products.html")

    products = read_products(csv_path)
    cache = load_cache()

    # 캐시에서 기존 번역 결과 복원
    for p in products:
        if p.code in cache:
            p.translations = cache[p.code]

    if html_only:
        print(f"[HTML 재생성] 캐시 {len(cache)}개 반영 중...")
        products.sort(key=lambda p: int(p.no) if p.no.isdigit() else 0)
        html = generate_html(products)
        with open(output_html, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"완료: {output_html}")
        return

    client = build_client()
    max_count = int(os.environ.get("MAX_TRANSLATE_ROWS", "20"))

    # 번역이 필요하지만 캐시에 없거나 누락 언어가 있는 제품 선별
    def needs_translation(p: ProductIntro) -> bool:
        if not p.kor_intro or not p.target_langs:
            return False
        needed = {LANG_MAP[l]["key"] for l in p.target_langs if l in LANG_MAP}
        cached = set(p.translations.keys())
        return bool(needed - cached)

    to_translate = [p for p in products if needs_translation(p)][:max_count]
    skip_count = len(products) - len(to_translate)

    print(f"총 {len(products)}개 제품 로드 완료.")
    print(f"신규·누락 번역 대상: {len(to_translate)}개 / 캐시 적용 또는 생략: {skip_count}개\n")

    success = fail = 0
    for idx, product in enumerate(to_translate, start=1):
        needed_langs = [l for l in product.target_langs if l in LANG_MAP
                        and LANG_MAP[l]["key"] not in product.translations]
        lang_labels = "+".join(needed_langs)
        print(
            f"[{idx:>3}/{len(to_translate)}] {product.code} | {product.name} "
            f"({lang_labels}) 번역 중...",
            end=" ", flush=True,
        )
        try:
            new_trans = translate_intro(client, product.kor_intro, needed_langs)
            product.translations.update(new_trans)
            cache[product.code] = product.translations
            save_cache(cache)
            print("완료")
            success += 1
        except Exception as exc:
            print(f"실패 → {exc}")
            fail += 1

    products.sort(key=lambda p: int(p.no) if p.no.isdigit() else 0)
    html = generate_html(products)
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n번역 완료: 성공 {success}개 / 실패 {fail}개")
    print(f"HTML 결과: {output_html}")


if __name__ == "__main__":
    main()
