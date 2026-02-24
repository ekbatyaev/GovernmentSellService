# # import zipfile
# # from lxml import etree
# # from pprint import pprint
# # from typing import Dict, List, Any
# #
# # # Namespace для 223-ФЗ TFF-16.0
# # NS = {
# #     "p": "http://zakupki.gov.ru/223fz/purchase/1",
# #     "t": "http://zakupki.gov.ru/223fz/types/1",
# #     "ns2": "http://zakupki.gov.ru/223fz/purchase/1",
# # }
# #
# # FILTERS = ["РОССЕТИ"]
# #
# #
# # def parse_lot(lot_elem) -> Dict[str, Any]:
# #     lot_data = lot_elem.find("./{*}lotData")
# #
# #     lot = {
# #         "guid": lot_elem.findtext("{*}guid"),
# #         "ordinalNumber": lot_elem.findtext("{*}ordinalNumber"),
# #         "cancelled": lot_elem.findtext("{*}cancelled") == "true",
# #         "deliveryPlaceIndication": lot_elem.findtext("{*}deliveryPlaceIndication"),
# #     }
# #
# #     if lot_data is None:
# #         return lot
# #
# #     lot["subject"] = lot_data.findtext("{*}subject")
# #     lot["initialSum"] = lot_data.findtext("{*}initialSum")
# #
# #     # Валюта
# #     currency = lot_data.find("{*}currency")
# #     if currency is not None:
# #         lot["currency"] = {
# #             "code": currency.findtext("{*}code"),
# #             "digitalCode": currency.findtext("{*}digitalCode"),
# #             "name": currency.findtext("{*}name"),
# #         }
# #
# #     # Место поставки
# #     delivery_place = lot_data.find("{*}deliveryPlace")
# #     if delivery_place is not None:
# #         lot["deliveryAddress"] = delivery_place.findtext("{*}address")
# #
# #     # Позиции
# #     lot_items = []
# #     for item in lot_data.findall(".//{*}lotItem"):
# #         lot_items.append({
# #             "guid": item.findtext("{*}guid"),
# #             "ordinalNumber": item.findtext("{*}ordinalNumber"),
# #             "okpd2_code": item.findtext("{*}okpd2/{*}code"),
# #             "okpd2_name": item.findtext("{*}okpd2/{*}name"),
# #             "okved2_code": item.findtext("{*}okved2/{*}code"),
# #             "okved2_name": item.findtext("{*}okved2/{*}name"),
# #             "okei_code": item.findtext("{*}okei/{*}code"),
# #             "okei_name": item.findtext("{*}okei/{*}name"),
# #             "qty": item.findtext("{*}qty"),
# #             "additionalInfo": item.findtext("{*}additionalInfo"),
# #         })
# #     lot["lotItems"] = lot_items
# #
# #     # Обеспечение заявки
# #     lot["applicationSupplyNeeded"] = lot_data.findtext("{*}applicationSupplyNeeded") == "true"
# #     lot["applicationSupplySumm"] = lot_data.findtext("{*}applicationSupplySumm")
# #     lot["applicationSupplyExtra"] = lot_data.findtext("{*}applicationSupplyExtra")
# #
# #     app_currency = lot_data.find("{*}applicationSupplyCurrency")
# #     if app_currency is not None:
# #         lot["applicationSupplyCurrency"] = {
# #             "code": app_currency.findtext("{*}code"),
# #             "digitalCode": app_currency.findtext("{*}digitalCode"),
# #             "name": app_currency.findtext("{*}name"),
# #         }
# #
# #     # Обеспечение исполнения
# #     lot["completingSupplyNeeded"] = lot_data.findtext("{*}completingSupplyNeeded") == "true"
# #
# #     comp_info = lot_data.find("{*}completingSupplyInfo")
# #     if comp_info is not None:
# #         lot["completingSupply"] = {
# #             "sum": comp_info.findtext("{*}sum"),
# #             "extra": comp_info.findtext("{*}extra"),
# #         }
# #
# #         comp_currency = comp_info.find("{*}currency")
# #         if comp_currency is not None:
# #             lot["completingSupply"]["currency"] = {
# #                 "code": comp_currency.findtext("{*}code"),
# #                 "digitalCode": comp_currency.findtext("{*}digitalCode"),
# #                 "name": comp_currency.findtext("{*}name"),
# #             }
# #
# #     # План
# #     plan_info = lot_elem.find("{*}lotPlanInfo")
# #     if plan_info is not None:
# #         lot["planInfo"] = {
# #             "planRegistrationNumber": plan_info.findtext("{*}planRegistrationNumber"),
# #             "planGuid": plan_info.findtext("{*}planGuid"),
# #             "positionNumber": plan_info.findtext("{*}positionNumber"),
# #             "positionGuid": plan_info.findtext("{*}positionGuid"),
# #         }
# #
# #     return lot
# #
# #
# # def parse_notification(root) -> Dict[str, Any]:
# #     data = {}
# #
# #     purchase_data = root.find(".//{*}purchaseNoticeData")
# #
# #     # Основная информация
# #     data["guid"] = root.findtext(".//{*}guid")
# #     data["createDateTime"] = root.findtext(".//{*}createDateTime")
# #     data["registrationNumber"] = root.findtext(".//{*}registrationNumber")
# #     data["name"] = root.findtext(".//{*}name")
# #     data["publicationDateTime"] = root.findtext(".//{*}publicationDateTime")
# #     data["urlEIS"] = root.findtext(".//{*}urlEIS")
# #     data["urlVSRZ"] = root.findtext(".//{*}urlVSRZ")
# #
# #     if purchase_data is not None:
# #         fields = [
# #             "modificationDate",
# #             "saveUserId",
# #             "deliveryPlaceIndication",
# #             "emergency",
# #             "jointPurchase",
# #             "hidePurchase",
# #             "changeDecisionDate",
# #             "antimonopolyDecisionTaken",
# #             "applSubmisionStartDate",
# #             "applSubmisionOrder",
# #             "summingupOrder",
# #             "submissionCloseDateTime",
# #             "publicationPlannedDate",
# #             "isLotOriented",
# #         ]
# #
# #         for f in fields:
# #             data[f] = purchase_data.findtext(f"{{*}}{f}")
# #
# #     # Электронная площадка
# #     ep = purchase_data.find("{*}electronicPlaceInfo") if purchase_data is not None else None
# #     if ep is not None:
# #         data["electronicPlace"] = {
# #             "name": ep.findtext("{*}name"),
# #             "url": ep.findtext("{*}url"),
# #             "electronicPlaceId": ep.findtext("{*}electronicPlaceId"),
# #         }
# #
# #     # Заказчик
# #     data["customerFullName"] = root.findtext(".//{*}customer/{*}mainInfo/{*}fullName")
# #     data["customerINN"] = root.findtext(".//{*}customer/{*}mainInfo/{*}inn")
# #     data["customerKPP"] = root.findtext(".//{*}customer/{*}mainInfo/{*}kpp")
# #     data["customerOGRN"] = root.findtext(".//{*}customer/{*}mainInfo/{*}ogrn")
# #
# #     # Контакт
# #     last = root.findtext(".//{*}contact/{*}lastName")
# #     first = root.findtext(".//{*}contact/{*}firstName")
# #     middle = root.findtext(".//{*}contact/{*}middleName")
# #
# #     if last or first:
# #         data["contactPerson"] = f"{last or ''} {first or ''} {middle or ''}".strip()
# #
# #     data["contactPhone"] = root.findtext(".//{*}contact/{*}phone")
# #     data["contactEmail"] = root.findtext(".//{*}contact/{*}email")
# #
# #     # Вложения
# #     attachments = []
# #     for doc in root.findall(".//{*}attachments/{*}document"):
# #         attachments.append({
# #             "guid": doc.findtext("{*}guid"),
# #             "fileName": doc.findtext("{*}fileName"),
# #             "description": doc.findtext("{*}description"),
# #             "url": doc.findtext("{*}url"),
# #             "contentUid": doc.findtext("{*}contentUid"),
# #         })
# #     data["attachments"] = attachments
# #
# #     # Лоты
# #     lots = []
# #     if purchase_data is not None:
# #         for lot_elem in purchase_data.findall(".//{*}lot"):
# #             lots.append(parse_lot(lot_elem))
# #     data["lots"] = lots
# #
# #     return data
# #
# #
# # def parse_zip_archive(zip_path: str) -> List[Dict[str, Any]]:
# #     """Парсинг всех XML файлов в ZIP архиве"""
# #     all_data = []
# #
# #     print(f"Открываем архив: {zip_path}")
# #
# #     with zipfile.ZipFile(zip_path, "r") as archive:
# #         xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]
# #         print(f"Найдено XML файлов: {len(xml_files)}")
# #
# #         for file_name in xml_files:
# #             print(f"Обработка: {file_name}")
# #
# #             with archive.open(file_name) as file:
# #                 try:
# #                     parser = etree.XMLParser(recover=True)
# #                     tree = etree.parse(file, parser)
# #                     root = tree.getroot()
# #
# #                     parsed = parse_notification(root)
# #                     parsed["sourceFile"] = file_name
# #
# #                     # Применяем фильтры
# #                     if parsed.get("customerFullName") and any(
# #                             filter_name in parsed["customerFullName"] for filter_name in FILTERS
# #                     ):
# #                         all_data.append(parsed)
# #                         print(f"  ✓ Добавлено (соответствует фильтру)")
# #                     else:
# #                         print(f"  ✗ Пропущено (не соответствует фильтру)")
# #
# #                 except Exception as e:
# #                     print(f"Ошибка в файле {file_name}: {e}")
# #
# #     print("Парсинг завершён.")
# #     return all_data
# #
# #
# # def print_purchase_summary(data: List[Dict[str, Any]]) -> None:
# #     """Вывод краткой информации о найденных закупках"""
# #     print(f"\n{'=' * 80}")
# #     print(f"НАЙДЕНО ЗАКУПОК: {len(data)}")
# #     print(f"{'=' * 80}")
# #
# #     for i, purchase in enumerate(data, 1):
# #         print(f"\n{i}. {purchase.get('name', 'Без названия')}")
# #         print(f"   Рег. номер: {purchase.get('registrationNumber', 'Н/Д')}")
# #         print(f"   Заказчик: {purchase.get('customerFullName', 'Н/Д')}")
# #         print(f"   Дата публикации: {purchase.get('publicationDateTime', 'Н/Д')}")
# #         print(f"   Лотов: {len(purchase.get('lots', []))}")
# #
# #         if purchase.get('lots'):
# #             total_sum = sum(float(lot.get('initialSum', 0)) for lot in purchase['lots'] if lot.get('initialSum'))
# #             print(f"   Общая сумма: {total_sum:,.2f} RUB")
# #
# #         print(f"   Файл: {purchase.get('sourceFile', 'Н/Д')}")
# #
# #
# # if __name__ == "__main__":
# #     zip_file_path = "019C77EE8318767AAB79CB88C90C110B.zip"
# #
# #     results = parse_zip_archive(zip_file_path)
# #
# #     print_purchase_summary(results)
# #
# #     # Если нужен подробный вывод
# #     print("\n" + "=" * 80)
# #     print("ИТОГ")
# #     print("=" * 80)
# #     pprint(results)
#
# import zipfile
# import xmltodict
# from pprint import pprint
# from typing import Dict, List, Any
#
# FILTERS = ["РОССЕТИ"]
#
#
# # ----------------------------
# # Удаление namespace из ключей
# # ----------------------------
# def remove_ns(obj):
#     if isinstance(obj, dict):
#         new_dict = {}
#         for k, v in obj.items():
#             clean_key = k.split(":")[-1]
#             new_dict[clean_key] = remove_ns(v)
#         return new_dict
#     elif isinstance(obj, list):
#         return [remove_ns(item) for item in obj]
#     else:
#         return obj
#
#
# # ----------------------------
# # Рекурсивный поиск ключа
# # ----------------------------
# def find_all_keys(obj, key):
#     results = []
#
#     if isinstance(obj, dict):
#         for k, v in obj.items():
#             if k == key:
#                 results.append(v)
#             results.extend(find_all_keys(v, key))
#
#     elif isinstance(obj, list):
#         for item in obj:
#             results.extend(find_all_keys(item, key))
#
#     return results
#
#
# # ----------------------------
# # Парсинг архива
# # ----------------------------
# def parse_zip_archive(zip_path: str) -> List[Dict[str, Any]]:
#     all_data = []
#
#     print(f"Открываем архив: {zip_path}")
#
#     with zipfile.ZipFile(zip_path, "r") as archive:
#         xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]
#         print(f"Найдено XML файлов: {len(xml_files)}")
#
#         for file_name in xml_files:
#             print(f"Обработка: {file_name}")
#
#             with archive.open(file_name) as file:
#                 try:
#                     xml_content = file.read()
#
#                     # XML → dict
#                     data = xmltodict.parse(xml_content)
#
#                     # Убираем namespace
#                     data = remove_ns(data)
#
#                     # Добавляем имя файла
#                     data["sourceFile"] = file_name
#
#                     # Фильтр по заказчику
#                     customer_names = find_all_keys(data, "fullName")
#
#                     if any(
#                         any(filter_name in str(name) for filter_name in FILTERS)
#                         for name in customer_names
#                     ):
#                         all_data.append(data)
#                         print("  ✓ Добавлено (соответствует фильтру)")
#                     else:
#                         print("  ✗ Пропущено (не соответствует фильтру)")
#
#                 except Exception as e:
#                     print(f"Ошибка в файле {file_name}: {e}")
#
#     print("Парсинг завершён.")
#     return all_data
#
#
# # ----------------------------
# # Краткий вывод
# # ----------------------------
# def print_purchase_summary(data: List[Dict[str, Any]]) -> None:
#     print(f"\n{'=' * 80}")
#     print(f"НАЙДЕНО ЗАКУПОК: {len(data)}")
#     print(f"{'=' * 80}")
#
#     for i, purchase in enumerate(data, 1):
#         names = find_all_keys(purchase, "name")
#         reg_numbers = find_all_keys(purchase, "registrationNumber")
#         customers = find_all_keys(purchase, "fullName")
#         sums = find_all_keys(purchase, "initialSum")
#
#         print(f"\n{i}. {names[0] if names else 'Без названия'}")
#         print(f"   Рег. номер: {reg_numbers[0] if reg_numbers else 'Н/Д'}")
#         print(f"   Заказчик: {customers[0] if customers else 'Н/Д'}")
#
#         if sums:
#             total = 0
#             for s in sums:
#                 try:
#                     total += float(s)
#                 except:
#                     pass
#             print(f"   Общая сумма: {total:,.2f} RUB")
#
#         print(f"   Файл: {purchase.get('sourceFile')}")
#
#
# # ----------------------------
# # MAIN
# # ----------------------------
# if __name__ == "__main__":
#     zip_file_path = "019C77EE8318767AAB79CB88C90C110B.zip"
#
#     results = parse_zip_archive(zip_file_path)
#
#     print_purchase_summary(results)
#
#     print("\n" + "=" * 80)
#     print("ИТОГ (первые 1 документ для примера)")
#     print("=" * 80)
#     if results:
#         pprint(results[0].keys())
import json
import zipfile
from pprint import pprint

import xmltodict
from typing import Dict, List, Any

# Фильтр по заказчику
FILTERS = ["РОССЕТИ"]


# ----------------------------
# Удаление namespace
# ----------------------------
def remove_ns(obj):
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            clean_key = k.split(":")[-1]
            new_dict[clean_key] = remove_ns(v)
        return new_dict
    elif isinstance(obj, list):
        return [remove_ns(item) for item in obj]
    else:
        return obj


# ----------------------------
# Если объект не список — делаем список
# ----------------------------
def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


# ----------------------------
# Нормализация одной закупки
# ----------------------------
def normalize_purchase(data: dict) -> dict:
    body = data.get("purchaseNotice", {}).get("body", {})
    item = body.get("item", {})
    notice = item.get("purchaseNoticeData", {})

    result = {}

    # --- Основная информация ---
    result["guid"] = item.get("guid")
    result["registration_number"] = notice.get("registrationNumber")
    result["name"] = notice.get("name")
    result["publication_datetime"] = notice.get("publicationDateTime")
    result["submission_close_datetime"] = notice.get("submissionCloseDateTime")

    # --- Заказчик ---
    customer = notice.get("customer", {}).get("mainInfo", {})
    result["customer"] = {
        "full_name": customer.get("fullName"),
        "inn": customer.get("inn"),
        "kpp": customer.get("kpp"),
        "ogrn": customer.get("ogrn"),
    }

    # --- Контакт ---
    contact = notice.get("contact", {})
    result["contact"] = {
        "last_name": contact.get("lastName"),
        "first_name": contact.get("firstName"),
        "middle_name": contact.get("middleName"),
        "phone": contact.get("phone"),
        "email": contact.get("email"),
    }

    # -- Подача заявки --

    result["apply_request"] = {
        "submission_order": notice.get("applSubmisionOrder"),
        "submission_place": notice.get("applSubmisionPlace"),
        "submission_start_date": notice.get("applSubmisionStartDate"),
    }

    # --- Лоты ---
    result["lots"] = []

    lots = ensure_list(notice.get("lots", {}).get("lot"))

    for lot in lots:
        lot_data = lot.get("lotData", {})

        lot_result = {
            "guid": lot.get("guid"),
            "ordinal_number": lot.get("ordinalNumber"),
            "subject": lot_data.get("subject"),
            "initial_summ": float(lot_data.get("initialSum", 0) or 0),
            "currency": lot_data.get("currency", {}).get("code"),
            "application_supply_summ": lot_data.get("applicationSupplySumm"),
            "application_supply_extra": lot_data.get("applicationSupplyExtra"),
            "completing_supply_summ": lot_data.get("completingSupplyInfo", {}).get("sum"),
            "items": []
        }

        lot_items = ensure_list(
            lot_data.get("lotItems", {}).get("lotItem")
        )

        for item in lot_items:
            lot_result["items"].append({
                "guid": item.get("guid"),
                "okpd2_code": item.get("okpd2", {}).get("code"),
                "okpd2_name": item.get("okpd2", {}).get("name"),
                "qty": item.get("qty"),
                "additional_info": item.get("additionalInfo"),
            })

        result["lots"].append(lot_result)
    result["initial_summ"] = result.get("lots")[0].get("initialSum")
    return result


# ----------------------------
# Парсинг ZIP архива
# ----------------------------
def parse_zip_archive(zip_path: str) -> List[Dict[str, Any]]:
    all_data = []

    print(f"Открываем архив: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as archive:
        xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]
        print(f"Найдено XML файлов: {len(xml_files)}")

        for file_name in xml_files:
            print(f"Обработка: {file_name}")

            with archive.open(file_name) as file:
                try:
                    xml_content = file.read()

                    # XML → dict
                    data = xmltodict.parse(xml_content)

                    # Убираем namespace
                    data = remove_ns(data)
                    pprint(data)

                    # Нормализация
                    normalized = normalize_purchase(data)
                    normalized["sourceFile"] = file_name

                    customer_name = normalized.get("customer", {}).get("full_name", "")

                    if any(f in str(customer_name) for f in FILTERS):
                        all_data.append(normalized)
                        print("  ✓ Добавлено (соответствует фильтру)")
                    else:
                        print("  ✗ Пропущено (не соответствует фильтру)")

                except Exception as e:
                    print(f"Ошибка в файле {file_name}: {e}")

    print("Парсинг завершён.")
    return all_data


# ----------------------------
# Краткий вывод
# ----------------------------
# def print_summary(data: List[Dict[str, Any]]) -> None:
#     print("\n" + "=" * 80)
#     print(f"НАЙДЕНО ЗАКУПОК: {len(data)}")
#     print("=" * 80)
#
#     for i, purchase in enumerate(data, 1):
#         print(f"\n{i}. {purchase.get('name')}")
#         print(f"   Рег. номер: {purchase.get('registrationNumber')}")
#         print(f"   Заказчик: {purchase.get('customer', {}).get('fullName')}")
#
#         total_sum = sum(lot.get("initialSum", 0) for lot in purchase.get("lots", []))
#         print(f"   Общая сумма лотов: {total_sum:,.2f} RUB")
#
#         for lot in purchase.get("lots", []):
#             print(f"      Лот {lot.get('ordinalNumber')} → {lot.get('subject')}")
#             print(f"         Сумма: {lot.get('initialSum'):,.2f}")
#             print(f"         Позиций: {len(lot.get('items', []))}")


# ----------------------------
# MAIN
# ----------------------------
if __name__ == "__main__":
    zip_file_path = "019C77EE8318767AAB79CB88C90C110B.zip"

    results = parse_zip_archive(zip_file_path)
    with open("results.json", 'w', encoding = 'utf-8') as file:
        json.dump(results, file, ensure_ascii = False, indent = 4)

    pprint(results)