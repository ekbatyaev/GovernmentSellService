export function getRegionNumbersByDistrict(districtName: string) {
  return REGION_CODES_BY_FEDERAL_DISTRICT[districtName] || [];
}

export function buildPurchaseRequestMeta(filters: {
  filterTypeName: string;
  districtName: string;
  regionNumber: string;
}) {
  const showDistrict = isOemOrItm(filters.filterTypeName);

  if (filters.regionNumber) {
    return {
      filter_type_name: filters.filterTypeName,
      region_numbers: [filters.regionNumber],
    };
  }

  if (showDistrict) {
    const regionNumbers = getRegionNumbersByDistrict(filters.districtName);

    return {
      filter_type_name: filters.filterTypeName,
      region_numbers: regionNumbers.length ? regionNumbers : undefined,
    };
  }

  return {
    filter_type_name: filters.filterTypeName,
    region_numbers: undefined,
  };
}

export function getDocumentDisplayName(document: unknown, index: number) {
  const item = document as Record<string, unknown>;

  return String(
    item.name ||
      item.file_name ||
      item.filename ||
      item.title ||
      item.document_name ||
      item.original_name ||
      `Документ ${index + 1}`,
  );
}

export function getDocumentDisplayMeta(document: unknown) {
  const item = document as Record<string, unknown>;

  const parts = [
    item.type ? `Тип: ${item.type}` : null,
    item.extension ? `Расширение: ${item.extension}` : null,
    item.size ? `Размер: ${item.size}` : null,
  ].filter(Boolean);

  return parts.join(" · ");
}