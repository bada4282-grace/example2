import csv
import os
from dataclasses import dataclass
from typing import Dict, List

from openai import OpenAI


@dataclass
class ProductIntro:
    """제품 소개 및 번역 결과를 보관하기 위한 데이터 구조."""

    no: str
    code: str
    name: str
    category: str
    spec: str
    target_market: str
    kor_intro: str
    translations: Dict[str, str]


def load_env() -> None:
    """환경 변수에서 OpenAI API 키를 불러온다."""

    # Windows / Linux 모두에서 .env 파일을 간단히 로드하기 위한 최소 구현
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


def translate_intro(
    client: OpenAI,
    text: str,
    src_lang: str = "Korean",
) -> Dict[str, str]:
    """한국어 제품 소개 문장을 영어, 중국어, 스페인어 B2B 바이어용 문체로 번역한다."""

    system_prompt = (
        "You are a senior B2B marketing copywriter and technical product marketer. "
        "You localize Korean industrial product descriptions into English, Simplified Chinese, "
        "and Latin American Spanish for professional buyers. "
        "Keep sentences concise but persuasive, highlight key specs and benefits, and use a "
        "business tone suitable for catalogs, proposals, and buyer communications. "
        "Do not add new specifications that are not in the source text."
    )

    user_prompt = (
        f"Source language: {src_lang}\n"
        "Source text (Korean product introduction):\n"
        f"{text}\n\n"
        "Tasks:\n"
        "1. Translate and localize into:\n"
        "   - English (for US/EU industrial buyers)\n"
        "   - Simplified Chinese (for Mainland China B2B buyers)\n"
        "   - Latin American Spanish (for B2B buyers in Mexico, Brazil, etc.)\n"
        "2. Use professional B2B business tone suitable for catalogs, proposals, and email to buyers.\n"
        "3. Focus on clear value proposition and key specs.\n"
        "4. Return JSON with keys: english, chinese, spanish. Do not include any other text."
    )

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )

    content = completion.choices[0].message.content
    if not content:
        raise RuntimeError("번역 결과를 받지 못했습니다.")

    import json

    data = json.loads(content)

    return {
        "english": data.get("english", "").strip(),
        "chinese": data.get("chinese", "").strip(),
        "spanish": data.get("spanish", "").strip(),
    }


def read_products(csv_path: str) -> List[ProductIntro]:
    """CSV 파일에서 한국어 제품 소개를 읽어온다.

    CP949(EUC-KR)로 먼저 시도하고, 실패 시 UTF-8-SIG, UTF-8 순서로 폴백한다.
    """

    products: List[ProductIntro] = []
    last_error: Exception | None = None

    for encoding in ("cp949", "utf-8-sig", "utf-8"):
        try:
            with open(csv_path, "r", encoding=encoding, newline="") as f:
                # 1행은 파일 제목(설명) 행이므로 건너뜀, 2행이 실제 컬럼 헤더
                next(f)
                reader = csv.DictReader(f)
                for row in reader:
                    products.append(
                        ProductIntro(
                            no=row.get("No", "") or row.get("\ufeffNo", ""),
                            code=row.get("품목코드", ""),
                            name=row.get("제품명", ""),
                            category=row.get("카테고리", ""),
                            spec=row.get("주요스펙", ""),
                            target_market=row.get("타겟시장", ""),
                            kor_intro=row.get("한국어소개", ""),
                            translations={},
                        )
                    )
            return products
        except UnicodeDecodeError as error:
            last_error = error
            products = []  # 다음 인코딩 시도 시 초기화
            continue

    raise RuntimeError(
        f"CSV 파일을 읽을 수 없습니다. 인코딩을 확인하세요. 마지막 오류: {last_error}"
    )


def generate_html(products: List[ProductIntro]) -> str:
    """원문과 번역문을 한눈에 볼 수 있는 HTML 문자열을 생성한다."""

    rows_html: List[str] = []
    for p in products:
        rows_html.append(
            "<tr>"
            f"<td>{p.no}</td>"
            f"<td>{p.code}</td>"
            f"<td>{p.name}</td>"
            f"<td>{p.category}</td>"
            f"<td>{p.spec}</td>"
            f"<td>{p.target_market}</td>"
            f"<td>{p.kor_intro}</td>"
            f"<td>{p.translations.get('english', '')}</td>"
            f"<td>{p.translations.get('chinese', '')}</td>"
            f"<td>{p.translations.get('spanish', '')}</td>"
            "</tr>"
        )

    body_rows = "\n".join(rows_html)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>제품 소개 다국어 번역 결과</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
            margin: 24px;
            background-color: #f4f5f7;
            color: #1f2933;
        }}
        h1 {{
            font-size: 24px;
            margin-bottom: 4px;
        }}
        p.subtitle {{
            margin-top: 0;
            margin-bottom: 16px;
            color: #6b7280;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #ffffff;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12);
            border-radius: 8px;
            overflow: hidden;
        }}
        thead {{
            background: #111827;
            color: #f9fafb;
        }}
        th, td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e5e7eb;
            vertical-align: top;
            font-size: 13px;
        }}
        th {{
            text-align: left;
            white-space: nowrap;
        }}
        tr:nth-child(even) {{
            background-color: #f9fafb;
        }}
        .lang-header {{
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>제품 소개 다국어 번역 결과</h1>
    <p class="subtitle">한국어 원문과 영어 / 중국어 / 스페인어 B2B 바이어용 번역을 한 번에 확인할 수 있습니다.</p>
    <table>
        <thead>
            <tr>
                <th>No</th>
                <th>품목코드</th>
                <th>제품명</th>
                <th>카테고리</th>
                <th>주요 스펙</th>
                <th>타겟 시장</th>
                <th class="lang-header">한국어 소개</th>
                <th class="lang-header">영어 (English)</th>
                <th class="lang-header">중국어 (简体中文)</th>
                <th class="lang-header">스페인어 (Español LATAM)</th>
            </tr>
        </thead>
        <tbody>
            {body_rows}
        </tbody>
    </table>
</body>
</html>
"""
    return html


def main() -> None:
    """CSV를 읽어 OpenAI API로 번역하고 HTML 결과 파일을 생성한다."""

    csv_path = os.path.join(os.path.dirname(__file__), "예제3.CSV")
    output_html = os.path.join(os.path.dirname(__file__), "translated_products.html")

    client = build_client()
    products = read_products(csv_path)

    # 데모 및 비용 절감을 위해 상위 몇 개만 번역하고 싶다면 아래 max_count 값을 조정
    max_count = int(os.environ.get("MAX_TRANSLATE_ROWS", "20"))
    translated_products: List[ProductIntro] = []

    for idx, product in enumerate(products):
        if not product.kor_intro:
            translated_products.append(product)
            continue

        if idx >= max_count:
            translated_products.append(product)
            continue

        translations = translate_intro(client, product.kor_intro)
        product.translations = translations
        translated_products.append(product)

    html = generate_html(translated_products)
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML 결과가 생성되었습니다: {output_html}")


if __name__ == "__main__":
    main()

