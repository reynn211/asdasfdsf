import { useMemo, useState } from "react";

const MIN_N = 5;
const MAX_N = 50;
const DEFAULT_N = 20;

export default function Histogram({ frequencies, totalWords }) {
  const [topN, setTopN] = useState(DEFAULT_N);

  const entries = useMemo(() => Object.entries(frequencies || {}), [frequencies]);
  const slice = useMemo(() => entries.slice(0, topN), [entries, topN]);
  const maxCount = slice.length > 0 ? slice[0][1] : 0;

  if (entries.length === 0) {
    return (
      <div className="placeholder">
        <h3>Нет данных для гистограммы</h3>
        <p>Загрузите файл, чтобы увидеть распределение частот.</p>
      </div>
    );
  }

  const effectiveMax = Math.min(MAX_N, entries.length);
  const effectiveN = Math.min(topN, effectiveMax);

  return (
    <div className="histogram">
      <div className="hist-controls">
        <label htmlFor="hist-n" className="hist-label">
          Топ-N: <strong>{effectiveN}</strong>
        </label>
        <input
          id="hist-n"
          type="range"
          min={MIN_N}
          max={effectiveMax}
          value={effectiveN}
          onChange={(e) => setTopN(Number(e.target.value))}
          className="hist-slider"
        />
        <span className="hist-meta">из {entries.length.toLocaleString("ru-RU")} уникальных</span>
      </div>

      <div className="hist-bars">
        {slice.map(([word, count], i) => {
          const barWidth = maxCount > 0 ? (count / maxCount) * 100 : 0;
          const share = totalWords > 0 ? (count / totalWords) * 100 : 0;
          return (
            <div className="hist-row" key={word}>
              <div className="hist-rank">{i + 1}</div>
              <div className="hist-word" title={word}>{word}</div>
              <div className="hist-bar-track">
                <div className="hist-bar-fill" style={{ width: `${barWidth}%` }} />
              </div>
              <div className="hist-count">
                {count.toLocaleString("ru-RU")}
                <span className="hist-share">{share.toFixed(1)}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
