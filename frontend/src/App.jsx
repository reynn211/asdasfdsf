import { useState, useEffect, useCallback, useMemo } from "react";
import "./App.css";
import Icon from "./components/Icon";
import Dropzone from "./components/Dropzone";
import FreqTable from "./components/FreqTable";
import FiltersPanel from "./components/FiltersPanel";
import Histogram from "./components/Histogram";
import Comparison from "./Comparison";

// In dev (`npm run dev`) we hit the FastAPI server directly on :8000.
// In the Docker build VITE_API_BASE is set to "" so the bundled app calls
// same-origin /api/* and nginx reverse-proxies to the backend container.
const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const DEFAULT_FILTERS = {
  excludeStopwords: true,
  language: "auto",
  minLength: 0,
  topN: 0,
  ignoreNumbers: true,
  ngram: 1,
  normalize: "stem",
};

export default function App() {
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastFile, setLastFile] = useState(null);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [showFilters, setShowFilters] = useState(false);
  const [activeView, setActiveView] = useState("table");
  const [compareSelection, setCompareSelection] = useState([]);
  const [comparePair, setComparePair] = useState([]);
  const [page, setPage] = useState("main");
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "light");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "light" ? "dark" : "light"));

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/history`, { credentials: "include" });
      if (res.ok) setHistory(await res.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const runAnalyze = async (file, useFilters) => {
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("exclude_stopwords", useFilters.excludeStopwords);
      form.append("language", useFilters.language);
      form.append("min_length", String(useFilters.minLength));
      form.append("top_n", String(useFilters.topN));
      form.append("ignore_numbers", useFilters.ignoreNumbers);
      form.append("ngram", String(useFilters.ngram));
      form.append("normalize", useFilters.normalize);
      const res = await fetch(`${API}/api/analyze`, {
        method: "POST",
        body: form,
        credentials: "include",
      });
      if (!res.ok) {
        let message;
        if (res.status === 413) {
          message = "Файл слишком большой (максимум 50 МБ)";
        } else {
          try {
            const data = await res.json();
            message = data.error || `Ошибка сервера (${res.status})`;
          } catch {
            message = `Ошибка сервера (${res.status})`;
          }
        }
        throw new Error(message);
      }
      const data = await res.json();
      setResult({ filename: file.name, ...data });
      fetchHistory();
    } catch (e) {
      setError(e.message || "Не удалось загрузить файл. Проверьте соединение.");
    } finally {
      setLoading(false);
    }
  };

  const handleFile = (file, errorMessage) => {
    if (errorMessage) {
      setError(errorMessage);
      return;
    }
    setLastFile(file);
    runAnalyze(file, filters);
  };

  const applyFilters = (newFilters) => {
    setFilters(newFilters);
    if (lastFile) runAnalyze(lastFile, newFilters);
  };

  const resetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    if (lastFile) runAnalyze(lastFile, DEFAULT_FILTERS);
  };

  const deleteEntry = async (id) => {
    await fetch(`${API}/api/history/${id}`, {
      method: "DELETE",
      credentials: "include",
    });
    fetchHistory();
    if (result && result.id === id) setResult(null);
    setCompareSelection((prev) => prev.filter((x) => x !== id));
  };

  const loadFromHistory = async (entry) => {
    // Re-analysis needs the original file bytes (not stored server-side), so
    // viewing a history entry must drop lastFile — otherwise Apply would
    // re-run the analyzer on whatever was last uploaded, not what's shown.
    setLastFile(null);
    setError(null);
    try {
      const res = await fetch(`${API}/api/history/${entry.id}`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`Ошибка сервера (${res.status})`);
      const data = await res.json();
      setResult({ filename: entry.filename, id: entry.id, ...data.result });
    } catch (e) {
      setError(e.message || "Не удалось загрузить запись из истории");
    }
  };

  const newFile = () => {
    setResult(null);
    setLastFile(null);
    setShowFilters(false);
    setActiveView("table");
  };

  const toggleCompare = (id) => {
    setCompareSelection((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  };

  // When two history entries are selected, fetch both full results and enter
  // compare mode. /api/history is summary-only now, so the heavy payload
  // comes in here on demand instead of on every list render.
  useEffect(() => {
    if (compareSelection.length !== 2) {
      setComparePair([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const fetched = await Promise.all(
          compareSelection.map(async (id) => {
            const meta = history.find((h) => h.id === id);
            if (!meta) return null;
            const res = await fetch(`${API}/api/history/${id}`, {
              credentials: "include",
            });
            if (!res.ok) return null;
            const data = await res.json();
            return { id, filename: meta.filename, result: data.result };
          })
        );
        if (cancelled) return;
        const valid = fetched.filter(Boolean);
        if (valid.length === 2) {
          setComparePair(valid);
          setPage("compare");
        }
      } catch {
        /* ignore — user can retry */
      }
    })();
    return () => { cancelled = true; };
  }, [compareSelection, history]);

  const exitCompare = () => setPage("main");



  const topWord = useMemo(() => {
    if (!result) return null;
    const entries = Object.entries(result.frequencies);
    return entries[0] || null;
  }, [result]);

  const ngramView = useMemo(() => {
    if (!result?.ngrams) return null;
    const keys = Object.keys(result.ngrams);
    if (keys.length === 0) return null;
    const n = keys[0];
    const entries = Object.entries(result.ngrams[n] || {});
    if (entries.length === 0) return null;
    return { n, entries };
  }, [result]);

  const fmt = (n) => (n == null ? "—" : n.toLocaleString("ru-RU"));

  const languageLabel = (code) => {
    if (code === "ru") return "Русский";
    if (code === "en") return "English";
    return "—";
  };

  const fleschLabel = (score) => {
    if (score == null) return "";
    if (score >= 80) return "очень легко";
    if (score >= 60) return "легко";
    if (score >= 40) return "средне";
    if (score >= 20) return "сложно";
    return "очень сложно";
  };

  const readability = result?.readability;

  if (page === "compare" && comparePair.length === 2) {
    return (
      <div className="app">
        <header className="topbar">
          <div className="brand">
            <span className="brand-mark">Ч</span>
            ЧастоСлов
          </div>
          <div className="top-actions">
            <button className="btn ghost sm" onClick={exitCompare}>
              <Icon name="x" size={13} />
              Закрыть сравнение
            </button>
            <button className="btn ghost sm" onClick={toggleTheme} aria-label="Сменить тему">
              <Icon name={theme === "light" ? "moon" : "sun"} size={13} />
            </button>
          </div>
        </header>
        <main className="container">
          <Comparison entries={comparePair} />
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">Ч</span>
          ЧастоСлов
        </div>
        <div className="top-actions">
          {result && (
            <button className="btn ghost sm" onClick={newFile}>
              <Icon name="upload" size={13} />
              Новый файл
            </button>
          )}
          <button className="btn ghost sm" onClick={toggleTheme} aria-label="Сменить тему">
            <Icon name={theme === "light" ? "moon" : "sun"} size={13} />
          </button>
        </div>
      </header>

      <main className="container">
        {!result && (
          <section className="hero">
            <h1 className="h1">Анализатор частоты слов</h1>
            <p className="sub">
              Загрузите .txt, .docx или .pdf документ — получите статистику,
              сортируемую таблицу и экспорт в CSV/XLSX/JSON за секунды.
            </p>
            <Dropzone onFile={handleFile} loading={loading} />
          </section>
        )}

        {error && (
          <div className="error" role="alert">
            <Icon name="x" size={14} />
            <span>{error}</span>
            <button className="error-dismiss" onClick={() => setError(null)} aria-label="Закрыть">
              ×
            </button>
          </div>
        )}

        {result && (
          <section className="results-screen">
            <div className="result-bar">
              <div className="file-pill">
                <div className="fic"><Icon name="file" size={16} /></div>
                <div className="file-pill-body">
                  <div className="fname">{result.filename}</div>
                  <div className="fmeta">
                    {fmt(result.total_words)} слов · {fmt(result.unique_words)} уникальных
                  </div>
                </div>
              </div>
              {result.id != null && (
                <div className="export-buttons">
                  <a className="btn ghost sm" href={`${API}/api/export/${result.id}?format=csv`}>CSV</a>
                  <a className="btn ghost sm" href={`${API}/api/export/${result.id}?format=xlsx`}>XLSX</a>
                  <a className="btn ghost sm" href={`${API}/api/export/${result.id}?format=json`}>JSON</a>
                </div>
              )}
            </div>

            <div className="kpis">
              <div className="kpi">
                <div className="kpi-label">Всего слов</div>
                <div className="kpi-value">{fmt(result.total_words)}</div>
                <div className="kpi-sub">100%</div>
              </div>
              <div className="kpi">
                <div className="kpi-label">Уникальных</div>
                <div className="kpi-value">{fmt(result.unique_words)}</div>
                <div className="kpi-sub">
                  {result.total_words > 0
                    ? `${((result.unique_words / result.total_words) * 100).toFixed(1)}%`
                    : "—"}
                </div>
              </div>
              <div className="kpi accent">
                <div className="kpi-label">Топ-1 слово</div>
                <div className="kpi-value">{topWord ? topWord[0] : "—"}</div>
                <div className="kpi-sub">{topWord ? `${fmt(topWord[1])} раз` : "—"}</div>
              </div>
            </div>

            {(result.language || readability) && (
              <div className="readability-strip">
                {result.language && (
                  <div className="rs-item">
                    <span className="rs-label">Язык</span>
                    <span className="rs-value">{languageLabel(result.language)}</span>
                  </div>
                )}
                {readability && (
                  <>
                    <div className="rs-item">
                      <span className="rs-label">Flesch</span>
                      <span className="rs-value">
                        {readability.flesch != null ? readability.flesch.toFixed(1) : "—"}
                        <span className="rs-hint">{fleschLabel(readability.flesch)}</span>
                      </span>
                    </div>
                    <div className="rs-item">
                      <span className="rs-label">Ср. длина слова</span>
                      <span className="rs-value">
                        {readability.avg_word_length != null
                          ? readability.avg_word_length.toFixed(2)
                          : "—"}
                      </span>
                    </div>
                    <div className="rs-item">
                      <span className="rs-label">Слов в предложении</span>
                      <span className="rs-value">
                        {readability.avg_sentence_length != null
                          ? readability.avg_sentence_length.toFixed(1)
                          : "—"}
                      </span>
                    </div>
                  </>
                )}
              </div>
            )}

            <div className="view-tabs">
              <button
                className={`vtab ${activeView === "table" ? "on" : ""}`}
                onClick={() => setActiveView("table")}
              >
                <Icon name="table" size={14} /> Таблица
              </button>
              <button
                className={`vtab ${activeView === "chart" ? "on" : ""}`}
                onClick={() => setActiveView("chart")}
              >
                <Icon name="chart" size={14} /> Гистограмма
              </button>
            </div>

            {activeView === "table" && (
              <>
                <FreqTable
                  frequencies={result.frequencies}
                  totalWords={result.total_words}
                  filterInfo={filters}
                />
                {ngramView && (
                  <div className="ngrams-section">
                    <h3 className="panel-title">
                      Топ {ngramView.n === "2" ? "биграмм" : "триграмм"}
                      <span className="ng-meta">
                        · {ngramView.entries.length.toLocaleString("ru-RU")} уникальных фраз
                      </span>
                    </h3>
                    <div className="freq-table">
                      <table>
                        <thead>
                          <tr>
                            <th className="rank">№</th>
                            <th>Фраза</th>
                            <th style={{ textAlign: "right" }}>Кол-во</th>
                          </tr>
                        </thead>
                        <tbody>
                          {ngramView.entries.slice(0, 20).map(([phrase, count], i) => (
                            <tr key={phrase}>
                              <td className="rank">{i + 1}</td>
                              <td><span className="word">{phrase}</span></td>
                              <td className="count">{count.toLocaleString("ru-RU")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {ngramView.entries.length > 20 && (
                      <div className="table-foot">
                        Показаны топ 20 из {ngramView.entries.length.toLocaleString("ru-RU")}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
            {activeView === "chart" && (
              <Histogram
                frequencies={result.frequencies}
                totalWords={result.total_words}
              />
            )}

            <button
              className="btn ghost sm filters-toggle"
              onClick={() => setShowFilters((s) => !s)}
            >
              <Icon name="filter" size={13} />
              {showFilters ? "Скрыть фильтры" : "Фильтры обработки"}
            </button>
            {showFilters && (
              <FiltersPanel
                values={filters}
                loading={loading}
                canReanalyze={!!lastFile}
                onApply={applyFilters}
                onReset={resetFilters}
              />
            )}
          </section>
        )}

        {history.length > 0 && (
          <section className="history">
            <h2 className="panel-title">История анализов · {history.length}</h2>
            <div className="history-list">
              {history.map((entry) => {
                const active = result && result.id === entry.id;
                const selected = compareSelection.includes(entry.id);
                return (
                  <div key={entry.id} className={`hist-item ${active ? "on" : ""}`}>
                    <button
                      className="hi-ic"
                      onClick={() => loadFromHistory(entry)}
                      title="Открыть"
                    >
                      <Icon name="file" size={14} />
                    </button>
                    <div
                      className="hi-body"
                      onClick={() => loadFromHistory(entry)}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="hi-name">{entry.filename}</div>
                      <div className="hi-meta">
                        {fmt(entry.total_words)} слов ·{" "}
                        {new Date(entry.created_at).toLocaleDateString("ru-RU", {
                          day: "2-digit",
                          month: "short",
                        })}
                      </div>
                    </div>
                    <button
                      className={`compare-btn ${selected ? "active" : ""}`}
                      onClick={() => toggleCompare(entry.id)}
                      title="Добавить к сравнению (нужно выбрать два)"
                    >
                      <Icon name="swap" size={13} />
                    </button>
                    <button
                      className="hi-del"
                      onClick={() => deleteEntry(entry.id)}
                      title="Удалить"
                    >
                      <Icon name="trash" size={13} />
                    </button>
                  </div>
                );
              })}
            </div>
            {compareSelection.length === 1 && (
              <p className="compare-hint">Выберите ещё одну запись для сравнения</p>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
