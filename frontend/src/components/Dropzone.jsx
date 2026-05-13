import { useState, useRef } from "react";
import Icon from "./Icon";

const ALLOWED_EXTENSIONS = [".txt", ".docx", ".pdf"];

export default function Dropzone({ onFile, loading }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const validate = (file) => {
    const lower = file.name.toLowerCase();
    return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
  };

  const handle = (file) => {
    if (!file) return;
    if (!validate(file)) {
      onFile(null, "Поддерживаются только .txt, .docx и .pdf файлы");
      return;
    }
    onFile(file);
  };

  return (
    <div
      className={`dropzone ${dragging ? "dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handle(e.dataTransfer.files[0]);
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
    >
      <div className="dz-icon">
        <Icon name="upload" size={28} />
      </div>
      <h2 className="dz-title">
        {loading ? "Анализируем..." : "Перетащите файл сюда"}
      </h2>
      <p className="dz-sub">или выберите его на компьютере. Максимум 50 МБ.</p>
      <button
        type="button"
        className="btn"
        disabled={loading}
        onClick={(e) => {
          e.stopPropagation();
          inputRef.current?.click();
        }}
      >
        <Icon name="upload" size={14} />
        Выбрать файл
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={ALLOWED_EXTENSIONS.join(",")}
        onChange={(e) => handle(e.target.files[0])}
        hidden
      />
      <div className="formats">
        {ALLOWED_EXTENSIONS.map((ext) => (
          <span key={ext} className="fmt">{ext}</span>
        ))}
      </div>
    </div>
  );
}
