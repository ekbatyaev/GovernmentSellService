import zipfile
from lxml import etree
from pprint import pprint


# Namespace словарь для zakupki.gov.ru
NS = {
    "ns3": "http://zakupki.gov.ru/oos/export/1",
    "ns5": "http://zakupki.gov.ru/oos/EPtypes/1",
    "ns4": "http://zakupki.gov.ru/oos/common/1",
    "ns2": "http://zakupki.gov.ru/oos/base/1",
}


def parse_notification(root):
    """
    Парсинг одного XML документа (root уже получен)
    """

    data = {}

    # Основная информация
    data["id"] = root.findtext(".//ns5:id", namespaces=NS)
    data["externalId"] = root.findtext(".//ns5:externalId", namespaces=NS)
    data["purchaseNumber"] = root.findtext(".//ns5:purchaseNumber", namespaces=NS)
    data["publishDate"] = root.findtext(".//ns5:publishDTInEIS", namespaces=NS)
    data["purchaseObject"] = root.findtext(".//ns5:purchaseObjectInfo", namespaces=NS)

    # Способ закупки
    data["placingWay"] = root.findtext(".//ns5:placingWay/ns2:name", namespaces=NS)

    # Площадка
    data["etpName"] = root.findtext(".//ns5:ETP/ns2:name", namespaces=NS)
    data["etpUrl"] = root.findtext(".//ns5:ETP/ns2:url", namespaces=NS)

    # Организация
    data["orgFullName"] = root.findtext(".//ns5:responsibleOrgInfo/ns5:fullName", namespaces=NS)
    data["orgINN"] = root.findtext(".//ns5:responsibleOrgInfo/ns5:INN", namespaces=NS)

    # Контактное лицо
    last = root.findtext(".//ns4:lastName", namespaces=NS)
    first = root.findtext(".//ns4:firstName", namespaces=NS)
    middle = root.findtext(".//ns4:middleName", namespaces=NS)

    if last or first:
        data["contactPerson"] = f"{last or ''} {first or ''} {middle or ''}".strip()
    else:
        data["contactPerson"] = None

    data["contactEmail"] = root.findtext(".//ns5:contactEMail", namespaces=NS)
    data["contactPhone"] = root.findtext(".//ns5:contactPhone", namespaces=NS)

    # Вложения
    attachments = []
    for att in root.findall(".//ns4:attachmentInfo", namespaces=NS):
        attachments.append({
            "fileName": att.findtext("ns4:fileName", namespaces=NS),
            "description": att.findtext("ns4:docDescription", namespaces=NS),
            "url": att.findtext("ns4:url", namespaces=NS),
            "size": att.findtext("ns4:fileSize", namespaces=NS),
        })

    data["attachments"] = attachments

    return data


def parse_zip_archive(zip_path):
    """
    Полный процесс:
    - открывает архив
    - обрабатывает все XML
    - возвращает список результатов
    """

    all_data = []

    print(f"Открываем архив: {zip_path}")

    with zipfile.ZipFile(zip_path, 'r') as archive:

        xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]

        print(f"Найдено XML файлов: {len(xml_files)}")

        for file_name in xml_files:
            print(f"Обработка: {file_name}")

            with archive.open(file_name) as file:
                try:
                    tree = etree.parse(file)
                    root = tree.getroot()

                    parsed = parse_notification(root)
                    parsed["sourceFile"] = file_name

                    all_data.append(parsed)

                except Exception as e:
                    print(f"Ошибка в файле {file_name}: {e}")

    print("Парсинг завершён.")
    return all_data


if __name__ == "__main__":
    zip_file_path = "019C7609AD1E7C6EBCD68DB939E18B47.zip"

    results = parse_zip_archive(zip_file_path)

    print("\nИТОГ:")
    pprint(results)