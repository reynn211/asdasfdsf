import { useMemo, useState } from "react";
import Icon from "./Icon";

const RENDER_OPTIONS = [50, 100, 250, 500, 1000];

export default function FreqTable({ frequencies, totalWords, filterInfo }) {
  const [sortBy, setSortBy] = useState("count");
  const [sortDir, setSortDir] = useState("desc");
  const [search, setSearch] = useState("");
  const [renderLimit, setRenderLimit] = useState(50);

  const allEntries = useMemo(() => Object.entries(frequencies || {}), [frequencies]);
  const maxCount = useMemo(() => {
    let m = 0;
    for (const [, c] of allEntries) if (c > m) m = c;
    return m;
  }, [allEntries]);

  const filteredSorted = useMemo(() => {
    const q = search.trim().toLowerCase();
    let entries = q ? allEntries.filter(([w]) => w.includes(q)) : allEntries;
    entries = [...entries];
    entries.sort(([wa, ca], [wb, cb]) => {
      const cmp = sortBy === "word" ? wa.localeCompare(wb) : ca - cb;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return entries;
  }, [allEntries, search, sortBy, sortDir]);

  const visible = filteredSorted.slice(0, renderLimit);

  const toggleSort = (col) => {
    if (sortBy === col) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortBy(col);
      setSortDir(col === "word" ? "asc" : "desc");
    }
  };
  const ind = (col) => (sortBy === col ? (sortDir === "asc" ? " ▲" : " ▼") : "");

  return (
    <>
      <div className="table-controls">
        <div className="search-box">
          <Icon name="search" size={13} />
          <input
            type="search"
            placeholder="Поиск по слову…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {filterInfo.excludeStopwords && (
          <span className="chip">
            <Icon name="check" size={11} /> Стоп-слова исключены
          </span>
        )}
        {filterInfo.ignoreNumbers && (
          <span className="chip">
            <Icon name="check" size={11} /> Без чисел
          </span>
        )}
        {filterInfo.normalize === "stem" && (
          <span className="chip">
            <Icon name="check" size={11} /> Стемминг
          </span>
        )}
        {filterInfo.minLength > 0 && (
          <span className="chip">
            <Icon name="check" size={11} /> Длина ≥ {filterInfo.minLength}
          </span>
        )}
        {filterInfo.topN > 0 && (
          <span className="chip">
            <Icon name="check" size={11} /> Топ {filterInfo.topN} (сервер)
          </span>
        )}
        <select
          className="chip-select"
          value={renderLimit}
          onChange={(e) => setRenderLimit(Number(e.target.value))}
          title="Сколько строк показывать"
        >
          {RENDER_OPTIONS.map((n) => (
            <option key={n} value={n}>Показать {n}</option>
          ))}
          <option value={Number.MAX_SAFE_INTEGER}>Показать все</option>
        </select>
      </div>

      <div className="freq-table">
        <table>
          <thead>
            <tr>
              <th className="rank">№</th>
              <th className="sortable" onClick={() => toggleSort("word")}>
                Слово{ind("word")}
              </th>
              <th
                className="sortable"
                style={{ textAlign: "right" }}
                onClick={() => toggleSort("count")}
              >
                Кол-во{ind("count")}
              </th>
              <th>Доля</th>
            </tr>
          </thead>
          <tbody>
            {visible.map(([word, count], i) => {
              const share = totalWords > 0 ? (count / totalWords) * 100 : 0;
              const barWidth = maxCount > 0 ? (count / maxCount) * 100 : 0;
              return (
                <tr key={word}>
                  <td className="rank">{i + 1}</td>
                  <td><span className="word">{word}</span></td>
                  <td className="count">{count.toLocaleString("ru-RU")}</td>
                  <td>
                    <div className="pct-cell">
                      <div className="pct">
                        <span style={{ width: `${barWidth}%` }} />
                      </div>
                      <span className="pct-label">{share.toFixed(2)}%</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="table-foot">
        Показано {visible.length.toLocaleString("ru-RU")} из {filteredSorted.length.toLocaleString("ru-RU")}
        {search && ` (фильтр по «${search}»)`}
        {filteredSorted.length > visible.length &&
          " — увеличьте лимит через селектор выше"}
      </div>
    </>
  );
}
