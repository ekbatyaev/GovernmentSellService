import asyncio
import json
import os
from typing import Dict
from dotenv import load_dotenv
from openai import AsyncOpenAI

JSON_SCHEMA = {
    "name": "doc_field_extractor",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "Победитель": {
                "type": "string",
                "description": "Победитель закупки"
            },
            "ИНН": {
                "type": "string",
                "description": "ИНН победителя закупки"
            },
            "Итоговая цена контракта": {
                "type": "string",
                "description": "Итоговая цена закупки"
            },
            "Другие участники": {
                "type": "string",
                "description": "Другие участники закупки"
            }
        },
        "required": [
            "Победитель",
            "ИНН",
            "Итоговая цена контракта",
            "Другие участники"

        ],
        "additionalProperties": False
    }
}

def extract_json_text(raw_text: str) -> str:
    cleaned = raw_text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return cleaned

async def itm_get_model_extraction(message) -> Dict:
    load_dotenv()

    api_key = os.getenv("YANDEX_CLOUD_API_KEY")
    folder_id = os.getenv("YANDEX_CLOUD_FOLDER")
    model_alias = os.getenv("YANDEX_CLOUD_MODEL", "yandexgpt")

    if not all([api_key, folder_id]):
        print(
            "Убедитесь, что в .env заданы YANDEX_CLOUD_API_KEY, YANDEX_CLOUD_FOLDER"
        )
        return {"model_answer": "Убедитесь, что в .env заданы YANDEX_CLOUD_API_KEY, YANDEX_CLOUD_FOLDER.", "error": True }

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://rest-assistant.api.cloud.yandex.net/v1",
        project=folder_id,
        timeout=120,
    )

    response = await client.responses.create(
        model=f"gpt://{folder_id}/{model_alias}",
        instructions=(
            """Ты эксперт по тендерным закупкам - тебе нужно из присланного текста выявить следующие поля:
            Победитель,ИНН,Итоговая цена контракта,Другие участники
            
            Ты должен вернуть мне словарь, в котором у каждого этого поля будет string значение, при этом, если этих данных нет в тексте, ты должен вернуть пустой string

            ПРИМЕР ТЕКСТА:
            
            Наименование предмета договора (лота): «Поставка ИБП» (ОКПД 2 - 26.20.40.111)
            Максимальная цена (сумма) договора: 12 457 768 (Двенадцать миллионов четыреста пятьдесят семь тысяч семьсот шестьдесят восемь) рублей 80 копеек.
            Повестка дня: Рассмотрение вопроса об утверждении единственного поставщика АО "Абсолютные Технологии" на право заключения договора.
            Решение заседания комиссии: заключить договор поставки с АО "Абсолютные Технологии".
            Сведения о поставщике:
            АО "Абсолютные Технологии"
            Адрес (место нахождения): 125167, г. Москва,
            Авиационный пер, д. 5, комн. 123
            Почтовый адрес: 125167, г. Москва, а/я 82
            ИНН 7714259315
            КПП 771401001
            ОГРН 1027739322082
            ОКПО 58488199

            ПРИМЕР ОТВЕТА:
            {
              "Победитель": "АО \"Абсолютные Технологии\"",
              "ИНН": "7714259315",
              "Итоговая цена контракта": "12457768.80"
              "Другие участники": ""
            }
            """
        ),
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Проанализируй следующий текст закупки и извлеки поля:\n\n{message}"
                    }
                ],
            }
        ],
        extra_body={
            "json_schema": JSON_SCHEMA,
        },
    )
    raw_output = response.output_text or ""
    json_text = extract_json_text(raw_output)
    try:
        parsed = json.loads(json_text)
        print("message")
        print(message)
        print("parsed")
        print(parsed)
        return parsed

    except json.JSONDecodeError as error:
        return {
            "error": error
        }


async def main():

    text = """Протокол № 229
    заседания комиссии ФКП «Ясень» по закупке у единственного поставщика

    г. Москва                                           «05» мая 2026 г.

    1. Наименование предмета договора (лота): «Поставка ИБП» (ОКПД 2 – 26.20.40.111)
    2. Максимальная цена (сумма) договора: 12 457 768 (Двенадцать миллионов четыреста пятьдесят семь тысяч семьсот шестьдесят восемь) рублей 80 копеек.
    3. Сведения о комиссии:
    Председателя комиссии – Сабанов А.Т.
    Заместитель председателя комиссии: Трацевский А.П.
    Члены комиссии- Каплин С.А., Блинов Д.Н.
    Секретарь комиссии: Перкатова Н.Э.
    Комиссия правомочна принимать решения по вопросам повестки дня.
    Заседание проходит по адресу: 108801, г. Москва, п. Сосенское, кв-л 105, дом 1, стр. 15, каб.210

    4. Повестка дня: Рассмотрение вопроса об утверждении единственного поставщика АО "Абсолютные Технологии" на право заключения договора.

    5. Обоснование: на основании пункта 38 статьи 17.1 Положения о закупке товаров, работ, услуг для нужд ФКП «Ясень».

    6. Решение заседания комиссии: заключить договор поставки с АО "Абсолютные Технологии".
    Решение принято единогласно.

    7. Сведения о поставщике (наименование единственного поставщика (исполнителя, подрядчика), юридический адрес, ИНН, КПП, ОГРН):

    АО "Абсолютные Технологии"
    Адрес (место нахождения): 125167, г. Москва,
    Авиационный пер, д. 5, комн. 123
    Почтовый адрес: 125167, г. Москва, а/я 82
    ИНН 7714259315
    КПП 771401001
    ОГРН 1027739322082
    ОКПО 58488199

    9. Настоящий протокол подлежит опубликованию на официальном сайте www.zakupki.gov.ru не позднее чем через 3 (три) дня со дня его подписания.
    Члены комиссии, присутствующие на заседании:"""

    single = await itm_get_model_extraction(text)


    print("\n=== SINGLE ===")
    print(single)


if __name__ == "__main__":
    asyncio.run(main())
