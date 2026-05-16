import { useMemo, useState } from "react";
import Icon from "./components/Icon";

const RENDER_OPTIONS = [50, 100, 250, 500, 1000];

const PRESENCE_OPTIONS = [
  { value: "all",    label: "Все слова" },
  { value: "common", label: "Общие (A и B)" },
  { value: "only_b", label: "Только в B" },
  { value: "only_a", label: "Только в A" },
];

export default function Comparison({ entries }) {
  const [a, b] = entries;
  const [search,      setSearch]      = useState("");
  const [sortBy,      setSortBy]      = useState("delta");
  const [sortDir,     setSortDir]     = useState("desc");
  const [presence,    setPresence]    = useState("all");
  const [renderLimit, setRenderLimit] = useState(50);

  const freqA = useMemo(() => a.result.frequencies || {}, [a.result.frequencies]);
  const freqB = useMemo(() => b.result.frequencies || {}, [b.result.frequencies]);

  const allWords = useMemo(
    () => new Set([...Object.keys(freqA), ...Object.keys(freqB)]),
    [freqA, freqB],
  );

  const kpis = useMemo(() => {
    let onlyA = 0, onlyB = 0, common = 0;
    for (const w of allWords) {
      const inA = freqA[w] != null;
      const inB = freqB[w] != null;
      if (inA && inB) common++;
      else if (inA) onlyA++;
      else onlyB++;
    }
    return { total: allWords.size, onlyA, onlyB, common };
  }, [allWords, freqA, freqB]);

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    const arr = [];
    for (const w of allWords) {
      if (q && !w.includes(q)) continue;
      const ca = freqA[w] || 0;
      const cb = freqB[w] || 0;
      if (presence === "only_a"  && cb !== 0) continue;
      if (presence === "only_b"  && ca !== 0) continue;
      if (presence === "common"  && (ca === 0 || cb === 0)) continue;
      arr.push({ word: w, a: ca, b: cb, delta: cb - ca });
    }
    arr.sort((x, y) => {
      let cmp;
      if      (sortBy === "word")  cmp = x.word.localeCompare(y.word);
      else if (sortBy === "a")     cmp = x.a - y.a;
      else if (sortBy === "b")     cmp = x.b - y.b;
      else                         cmp = x.delta - y.delta;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [allWords, freqA, freqB, search, sortBy, sortDir, presence]);

  const visible = rows.slice(0, renderLimit);

  const toggleSort = (col) => {
    if (sortBy === col) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortBy(col); setSortDir(col === "word" ? "asc" : "desc"); }
  };
  const ind = (col) => (sortBy === col ? (sortDir === "asc" ? " ▲" : " ▼") : "");
  const fmt = (n) => n.toLocaleString("ru-RU");

  const presenceLabel = PRESENCE_OPTIONS.find((o) => o.value === presence)?.label;

  return (
    <div className="results-screen comparison">

      {/* ── file pills ── */}
      <div className="result-bar cmp-result-bar">
        <div className="file-pill">
          <div className="fic"><Icon name="file" size={16} /></div>
          <div className="file-pill-body">
            <div className="fname">
              <span className="cmp-badge cmp-badge-a">A</span>
              {a.filename}
            </div>
            <div className="fmeta">
              {fmt(a.result.total_words ?? 0)} слов
              &nbsp;·&nbsp;
              {fmt(Object.keys(freqA).length)} уникальных
            </div>
          </div>
        </div>

        <div className="file-pill">
          <div className="fic"><Icon name="file" size={16} /></div>
          <div className="file-pill-body">
            <div className="fname">
              <span className="cmp-badge cmp-badge-b">B</span>
              {b.filename}
            </div>
            <div className="fmeta">
              {fmt(b.result.total_words ?? 0)} слов
              &nbsp;·&nbsp;
              {fmt(Object.keys(freqB).length)} уникальных
            </div>
          </div>
        </div>
      </div>

      {/* ── kpi cards ── */}
      <div className="kpis">
        <div className="kpi">
          <div className="kpi-label">Объединение</div>
          <div className="kpi-value">{fmt(kpis.total)}</div>
          <div className="kpi-sub">уникальных слов</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Общих слов</div>
          <div className="kpi-value">{fmt(kpis.common)}</div>
          <div className="kpi-sub">
            {kpis.total > 0
              ? `${((kpis.common / kpis.total) * 100).toFixed(1)}%`
              : "—"}
          </div>
        </div>
        <div className="kpi accent">
          <div className="kpi-label">Только в B</div>
          <div className="kpi-value">{fmt(kpis.onlyB)}</div>
          <div className="kpi-sub">
            {kpis.total > 0
              ? `${((kpis.onlyB / kpis.total) * 100).toFixed(1)}% новых`
              : "—"}
          </div>
        </div>
      </div>

      {/* ── table controls ── */}
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

        <select
          className="chip-select"
          value={presence}
          onChange={(e) => { setPresence(e.target.value); setRenderLimit(50); }}
          title="Фильтр по присутствию"
        >
          {PRESENCE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {presence !== "all" && (
          <span className="chip">
            <Icon name="filter" size={11} />
            {presenceLabel}
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

      {/* ── table ── */}
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
                onClick={() => toggleSort("a")}
              >
                A{ind("a")}
              </th>
              <th
                className="sortable"
                style={{ textAlign: "right" }}
                onClick={() => toggleSort("b")}
              >
                B{ind("b")}
              </th>
              <th
                className="sortable"
                style={{ textAlign: "right" }}
                onClick={() => toggleSort("delta")}
              >
                Δ (B−A){ind("delta")}
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r, i) => (
              <tr key={r.word}>
                <td className="rank">{i + 1}</td>
                <td><span className="word">{r.word}</span></td>
                <td className={`count${r.a === 0 ? " cmp-zero" : ""}`}>
                  {r.a === 0 ? "—" : fmt(r.a)}
                </td>
                <td className={`count${r.b === 0 ? " cmp-zero" : ""}`}>
                  {r.b === 0 ? "—" : fmt(r.b)}
                </td>
                <td className={`count ${
                  r.delta > 0 ? "delta-pos" : r.delta < 0 ? "delta-neg" : ""
                }`}>
                  {r.delta > 0
                    ? `+${fmt(r.delta)}`
                    : r.delta === 0
                    ? "0"
                    : fmt(r.delta)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="table-foot">
        Показано {fmt(visible.length)} из {fmt(rows.length)}
        {search && ` (фильтр по «${search}»)`}
        {rows.length > visible.length && " — увеличьте лимит через селектор выше"}
      </div>
    </div>
  );
}
