import httpx
from app.settings import settings, logger, async_client
from typing import Any, Optional, Dict


async def api_datum_query(token: str, endpoint: str, **filters: Any) -> Optional[Dict[str, Any]]:

    """
    Асинхронно получает список рассылок с сервера.
    :param token: токен авторизации
    :param filters: произвольные параметры фильтрации (передаются в JSON)
    :return: ответ сервера (словарь) или None в случае ошибки
    """

    url = f"{settings.app_url}{settings.app_base}/{endpoint}"
    payload = {"token": token, **filters}
    try:
        response = await async_client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code} - {e.response.text}")
    except httpx.TimeoutException:
        print("Request timed out")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return None

def put_purchase_to_db(purchase: dict) -> str:
    purchase_payload = dict(purchase)
    purchase_payload["token"] = TOKEN
    registration_number = purchase_payload.get("registration_number")
    guid = purchase_payload.get("guid")

    try:
        response = requests.post(
            f"{APP_URL}{API_BASE}/put_purchase",
            json=purchase_payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.exception(
            "Pipeline: ошибка запроса к API | reg=%s | guid=%s | error=%s",
            registration_number,
            guid,
            e,
        )
        return "skipped"
    except ValueError:
        logger.warning(
            "Pipeline: API вернул некорректный JSON | reg=%s | guid=%s",
            registration_number,
            guid,
        )
        return "skipped"

    message = data.get("message")

    if message == "Purchase updated":
        logger.info(
            "Pipeline: обновлена закупка через API | reg=%s | guid=%s",
            registration_number,
            guid,
        )
        return "updated"

    if message == "Purchase created":
        logger.info(
            "Pipeline: создана новая закупка через API | reg=%s | guid=%s",
            registration_number,
            guid,
        )
        return "created"

    logger.warning(
        "Pipeline: неизвестный ответ API | reg=%s | guid=%s | message=%s",
        registration_number,
        guid,
        message,
    )
    return "skipped"

def process_day(date_str: str, filter_number = 0) -> Dict:
    logger.info("Pipeline: обработка даты %s", date_str)

    registration_numbers_dict_per_day = {}

    for filter_name in REGIONS_OF_THE_FILTERS.keys():
        registration_numbers_dict_per_day[filter_name] = {}
        for region_code in REGIONS_OF_THE_FILTERS[filter_name]:
            registration_numbers_dict_per_day[filter_name][region_code] = {
                "created": [],
                "updated": [],
                "skipped": []
            }

    for region in ALL_REGION_CODES:

        result_purchases = get_docs_by_region(
            org_region=region,
            document_type="purchaseNotice",
            exact_date=date_str,
            subsystem_type="RI223",
        )

        archive_urls_purchases = result_purchases.get("archive_urls", [])
        for archive_url in archive_urls_purchases:
            zip_path_purchases = download_archive_from_result(archive_url)

            if zip_path_purchases is None:
                logger.info("Pipeline: скачивание архива не удалось")
                continue

            logger.info("Pipeline: архив закупок скачан: %s", zip_path_purchases)

            purchases = parse_zip_archive_purchases(zip_path_purchases, region, filter_number)

            logger.info("Pipeline: после фильтров закупок: %s", len(purchases))

            for purchase in purchases:
                try:
                    status = put_purchase_to_db(purchase)

                    registration_numbers_dict_per_day[purchase["filter_type_name"]][purchase["region_number"]][status].append(purchase["registration_number"])

                except Exception:
                    logger.exception(
                        "Pipeline: ошибка сохранения закупки | reg=%s | guid=%s",
                        purchase.get("registration_number"),
                        purchase.get("guid"),
                    )
                    registration_numbers_dict_per_day[purchase["filter_type_name"]][purchase["region_number"]][
                        "skipped"].append(purchase["registration_number"])


        result_protocols = get_docs_by_region(
            org_region=region,
            document_type="purchaseProtocol",
            exact_date=date_str,
            subsystem_type="RI223",
        )

        archive_urls_protocols = result_protocols.get("archive_urls", [])

        for archive_url in archive_urls_protocols:
            zip_path_protocols = download_archive_from_result(archive_url)

            if zip_path_protocols is None:
                logger.info("Pipeline: скачивание архива не удалось")
                continue

            logger.info("Pipeline: архив протоколов скачан: %s", zip_path_protocols)

            protocols = parse_zip_archive_protocols(zip_path_protocols, region, filter_number)

            logger.info("Pipeline: после фильтров протоколов: %s", len(protocols))

            for protocol in protocols:


                try:
                    response = requests.post(
                        f"{APP_URL}{API_BASE}/update_purchase",
                        json={
                            "token": TOKEN,
                            "registration_number": protocol["registration_number"],
                            "result_info": protocol["result_info"],
                            "documents_list": protocol["documents_list"],
                            "publication_datetime": protocol["publication_datetime"],
                        },
                        timeout=30,
                    )
                    response.raise_for_status()

                    database_answer = response.json()

                    if database_answer.get("message") == "Purchase not found" and not database_answer.get("data"):
                        try:
                            status = put_purchase_to_db(protocol)

                            registration_numbers_dict_per_day[protocol["filter_type_name"]][protocol["region_number"]][
                                status].append(protocol["registration_number"])

                            logger.info("Create purchase from protocol response | %s", response.text)

                            logger.info(
                                "Pipeline: протокол создал закупку | reg=%s",
                                protocol["registration_number"],
                            )
                        except Exception:
                            logger.exception(
                                "Pipeline: ошибка сохранения закупки | reg=%s | guid=%s",
                                protocol.get("registration_number"),
                                protocol.get("guid"),
                            )
                            registration_numbers_dict_per_day[protocol["filter_type_name"]][protocol["region_number"]][
                                "skipped"].append(protocol["registration_number"])
                        finally:
                            continue

                    registration_numbers_dict_per_day[protocol["filter_type_name"]][protocol["region_number"]][
                        "updated"].append(protocol["registration_number"])

                    logger.info("Update response | %s", response.text)

                    logger.info(
                        "Pipeline: протокол обновил закупку | reg=%s",
                        protocol["registration_number"],
                    )

                except Exception as error:
                    logger.exception(
                        "У заявки не обновились поля | reg=%s | error=%s",
                        protocol.get("registration_number"),
                        error,
                    )
                    registration_numbers_dict_per_day[protocol["filter_type_name"]][protocol["region_number"]][
                        "skipped"].append(protocol["registration_number"])

    return registration_numbers_dict_per_day

def create_analysis(rows, analysis_path):

    try:
        df = pd.DataFrame(rows)
        df.to_excel(analysis_path, index=False)

        wb = load_workbook(analysis_path)
        ws = wb.active

        header_fill = PatternFill("solid", fgColor="366092")
        header_font = Font(color="FFFFFF", bold=True)
        cell_font = Font(size=10)
        align = Alignment(wrap_text=True, vertical="center")
        thin_side = Side(style="thin")
        border = Border(
            left=thin_side,
            right=thin_side,
            top=thin_side,
            bottom=thin_side,
        )

        for col in range(1, ws.max_column + 1):
            c = ws.cell(1, col)
            c.font = header_font
            c.fill = header_fill
            c.alignment = align
            c.border = border

        for r in range(2, ws.max_row + 1):
            ws.row_dimensions[r].height = 30
            for c in range(1, ws.max_column + 1):
                cell = ws.cell(r, c)
                cell.font = cell_font
                cell.alignment = align
                cell.border = border

        for col in range(1, ws.max_column + 1):
            letter = get_column_letter(col)
            max_len = max(
                len(str(ws.cell(r, col).value or ""))
                for r in range(1, ws.max_row + 1)
            )
            ws.column_dimensions[letter].width = min(max_len + 2, 50)

        last = ws.max_row + 2
        ws.cell(last, 1, "Данные по закупкам, лотам и позициям")
        ws.merge_cells(
            start_row=last,
            start_column=1,
            end_row=last,
            end_column=ws.max_column,
        )

        footnote_cell = ws.cell(last, 1)
        footnote_cell.font = Font(italic=True, size=9, color="555555")
        footnote_cell.alignment = Alignment(horizontal="center")
        footnote_cell.border = Border(top=Side(style="thin", color="AAAAAA"))

        wb.save(analysis_path)
    except Exception as e:

        logger.info("Произошла ошибка при создании анализа")

def send_analysis(rows, emails, created, updated, skipped, extra_rows = None, path_name_extra = "all_purchases.xlsx"):

    html_content = f"""
                    <html><body style="font-family:Arial;">
                    <h2 style="color:#2E86C1;">Уведомление о заявках с госзакупок</h2>
                    <p>Новых заявок добавлено: <b style="color:#E74C3C;font-size:18px;">{created}</b></p>
                    <p>Заявок обновлено: <b style="color:#F39C12;font-size:18px;">{updated}</b></p>
                    <p>Пропущено: <b style="color:#7F8C8D;font-size:18px;">{skipped}</b></p>
                    <hr><p style="color:#888;font-size:12px;">Это письмо сформировано автоматически, отвечать на него не нужно</p>
                    </body></html>
                    """

    attachments = []

    analysis_path = "analysis.xlsx"

    create_analysis(rows, analysis_path = analysis_path)

    attachments.append(analysis_path)

    if extra_rows:

        create_analysis(extra_rows, analysis_path=path_name_extra)
        attachments.append(path_name_extra)

    now = datetime.now()

    subject = f"Заявки с госзакупок за {now.strftime('%d.%m.%Y')}"

    try:

        for email in emails:
            send_email(
                email,
                subject,
                html_content,
                attachments=attachments if (created or updated) else None,
            )

    finally:
        for path in attachments:
            if os.path.exists(path):
                os.remove(path)

