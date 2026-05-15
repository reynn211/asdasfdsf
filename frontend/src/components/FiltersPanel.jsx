import { useState, useEffect } from "react";
import Icon from "./Icon";

export default function FiltersPanel({ values, loading, canReanalyze, onApply, onReset }) {
  const [draft, setDraft] = useState(values);

  // Re-seed local state when parent applies new values (e.g. after Сбросить).
  useEffect(() => { setDraft(values); }, [values]);

  const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  return (
    <div className="filters-panel">
      <h3 className="panel-title">Фильтры обработки</h3>

      <div className="field-row">
        <div className="field">
          <label htmlFor="f-min">Минимальная длина слова</label>
          <input
            id="f-min"
            className="field-input"
            type="number"
            min="0"
            value={draft.minLength}
            onChange={(e) => set("minLength", Number(e.target.value) || 0)}
          />
        </div>
        <div className="field">
          <label htmlFor="f-top">Top-N (срез на сервере)</label>
          <input
            id="f-top"
            className="field-input"
            type="number"
            min="0"
            value={draft.topN}
            onChange={(e) => set("topN", Number(e.target.value) || 0)}
          />
        </div>
      </div>

      <div className="field-row">
        <div className="field">
          <label htmlFor="f-lang">Язык</label>
          <select
            id="f-lang"
            className="field-input"
            value={draft.language}
            onChange={(e) => set("language", e.target.value)}
          >
            <option value="auto">Авто</option>
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-ngram">N-граммы</label>
          <select
            id="f-ngram"
            className="field-input"
            value={draft.ngram}
            onChange={(e) => set("ngram", Number(e.target.value))}
          >
            <option value={1}>Только слова</option>
            <option value={2}>Биграммы</option>
            <option value={3}>Триграммы</option>
          </select>
        </div>
      </div>

      <div className="field" style={{ marginBottom: 6 }}>
        <label>Опции</label>
      </div>

      <label className="check-row" onClick={() => set("excludeStopwords", !draft.excludeStopwords)}>
        <span className={`cb ${draft.excludeStopwords ? "on" : ""}`}>
          {draft.excludeStopwords && <Icon name="check" size={11} strokeWidth="3" />}
        </span>
        Исключить стоп-слова
      </label>

      <label className="check-row" onClick={() => set("ignoreNumbers", !draft.ignoreNumbers)}>
        <span className={`cb ${draft.ignoreNumbers ? "on" : ""}`}>
          {draft.ignoreNumbers && <Icon name="check" size={11} strokeWidth="3" />}
        </span>
        Игнорировать числа
      </label>

      <label
        className="check-row"
        onClick={() => set("normalize", draft.normalize === "stem" ? "none" : "stem")}
        title="Сводит словоформы к общей основе (Porter для RU и EN)"
      >
        <span className={`cb ${draft.normalize === "stem" ? "on" : ""}`}>
          {draft.normalize === "stem" && <Icon name="check" size={11} strokeWidth="3" />}
        </span>
        Стемминг (Porter RU+EN)
      </label>

      <div className="panel-foot">
        <button className="btn ghost sm" type="button" onClick={onReset} disabled={loading}>
          Сбросить
        </button>
        <button
          className="btn sm"
          type="button"
          onClick={() => onApply(draft)}
          disabled={loading || !canReanalyze}
          title={!canReanalyze ? "Загрузите файл заново, чтобы применить фильтры" : undefined}
        >
          Применить
        </button>
      </div>
    </div>
  );
}
