# vk-nlp

## Запуск backend

```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
```

## Сборка C++ анализатора через CMake

```bash
cd backend
cmake -S . -B build
cmake --build build
```

Сборка использует структуру `backend/include` + `backend/src` и собирает бинарник `backend/analyzer` (`backend/analyzer.exe` на Windows).

## Запуск frontend

```bash
cd frontend && npm install && npm run dev
```
