import { useState, useEffect, useCallback } from "react";
import "./App.css";

const API = "http://localhost:8000";

export default function App() {
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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

  const uploadFile = async (file) => {
    if (!file.name.endsWith(".txt")) {
      setError("Поддерживаются только .txt файлы");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/api/analyze`, {
        method: "POST",
        body: form,
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Upload failed");
      }
      const data = await res.json();
      setResult({ filename: file.name, ...data });
      fetchHistory();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  };

  const onFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) uploadFile(file);
  };

  const deleteEntry = async (id) => {
    await fetch(`${API}/api/history/${id}`, {
      method: "DELETE",
      credentials: "include",
    });
    fetchHistory();
    if (result && result.id === id) setResult(null);
  };

  const loadFromHistory = (entry) => {
    setResult({ filename: entry.filename, ...entry.result });
  };

  return (
    <div className="app">
      <h1>Анализатор частоты слов</h1>

      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        {loading ? (
          <p>Анализируем...</p>
        ) : (
          <>
            <p>Перетащите .txt файл сюда</p>
            <label className="file-label">
              или выберите файл
              <input type="file" accept=".txt" onChange={onFileSelect} hidden />
            </label>
          </>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="results">
          <h2>{result.filename}</h2>
          <div className="stats">
            <span>Всего слов: {result.total_words}</span>
            <span>Уникальных слов: {result.unique_words}</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Слово</th>
                <th>Кол-во</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.frequencies)
                .slice(0, 50)
                .map(([word, count], i) => (
                  <tr key={word}>
                    <td>{i + 1}</td>
                    <td>{word}</td>
                    <td>{count}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {history.length > 0 && (
        <div className="history">
          <h2>История</h2>
          <ul>
            {history.map((entry) => (
              <li key={entry.id}>
                <button className="link-btn" onClick={() => loadFromHistory(entry)}>
                  {entry.filename}
                </button>
                <span className="date">{new Date(entry.created_at).toLocaleString()}</span>
                <button className="delete-btn" onClick={() => deleteEntry(entry.id)}>
                  &times;
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
