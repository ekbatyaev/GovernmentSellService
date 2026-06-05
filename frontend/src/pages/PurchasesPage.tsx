function DocumentsList({ documents }: { documents: unknown[] }) {
  const [isOpen, setIsOpen] = useState(false);
  const [isPurposeOpen, setIsPurposeOpen] = useState(true);

  if (!Array.isArray(documents) || documents.length === 0) {
    return (
      <Card>
        <div className="flex items-center gap-2 text-sm font-semibold">
          <FileText size={18} />
          Обработанные документы
        </div>
        <p className="mt-3 text-sm text-[color:var(--se-muted)]">
          Обработанные документы не найдены.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <button
        className="flex w-full items-center justify-between gap-3 text-left"
        onClick={() => setIsOpen((value) => !value)}
      >
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <FileText size={18} />
            Обработанные документы
          </div>
          <div className="mt-1 text-xs text-[color:var(--se-muted)]">
            Найдено: {documents.length}
          </div>
        </div>

        <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-[color:var(--se-techno-green)]">
          {isOpen ? "Скрыть" : "Показать"}
        </span>
      </button>

      {isOpen && (
        <div className="mt-4 divide-y divide-[color:var(--se-border)] rounded-2xl border border-[color:var(--se-border)] bg-white">
          {documents.map((document, index) => {
            const item = document as Record<string, unknown>;
            const name = getDocumentDisplayName(document, index);
            const meta = getDocumentDisplayMeta(document);
            const url = item.url || item.href || item.link;

            return (
              <div
                key={`${name}-${index}`}
                className="flex flex-col gap-2 px-4 py-3 md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <div className="text-sm font-semibold text-[color:var(--se-text)]">
                    {name}
                  </div>

                  {meta && (
                    <div className="mt-1 text-xs text-[color:var(--se-muted)]">
                      {meta}
                    </div>
                  )}
                </div>

                {url && (
                  <a
                    className="inline-flex items-center gap-2 text-sm font-semibold text-[color:var(--se-techno-green)] hover:underline"
                    href={String(url)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Открыть
                    <ExternalLink size={14} />
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}