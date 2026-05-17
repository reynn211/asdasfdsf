
import os
import re
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
import time


def load_dataset(path="medium_articles.csv", max_articles=50000, min_length=200):
    """Загружает датасет Medium Articles и возвращает очищенный текст."""
    import pandas as pd

    if not os.path.exists(path):
        print(f"[Данные] Файл '{path}' не найден.")
        print("Скачайте датасет с Kaggle: https://www.kaggle.com/datasets/fabiochiusano/medium-articles")
        print(f"Поместите CSV-файл как '{path}' в рабочую директорию.")
        raise FileNotFoundError(f"Файл данных '{path}' не найден")

    print(f"[Данные] Загрузка из {path}...")
    df = pd.read_csv(path, nrows=max_articles)

    if 'text' in df.columns:
        text_col = 'text'
    elif 'content' in df.columns:
        text_col = 'content'
    else:
        text_col = df.columns[-1]
        print(f"[Данные] Предупреждение: используется столбец '{text_col}'")

    texts = df[text_col].dropna().tolist()
    texts = [t for t in texts if len(t) >= min_length]
    corpus = "\n\n".join(texts[:max_articles])

    corpus = re.sub(r'[^\S\n]+', ' ', corpus)
    corpus = re.sub(r'\n{3,}', '\n\n', corpus)

    print(f"[Данные] Загружено {len(texts)} статей, общий объём: {len(corpus):,} символов")
    return corpus


class TextDataset(Dataset):
    """Датасет последовательностей для языковой модели."""

    def __init__(self, encoded_text, seq_length, stride=None):
        self.data = encoded_text
        self.seq_length = seq_length
        self.stride = stride if stride is not None else seq_length
        self.n_samples = max(0, (len(self.data) - self.seq_length - 1) // self.stride)

    def __len__(self):
        return self.n_samples

    def __getitem__(self, idx):
        start = idx * self.stride
        x = self.data[start:start + self.seq_length]
        y = self.data[start + 1:start + self.seq_length + 1]
        return torch.tensor(x, dtype=torch.long), torch.tensor(y, dtype=torch.long)


def create_dataloaders(encoded_text, seq_length, batch_size, train_ratio=0.9, stride=None):
    """Создает DataLoader'ы для обучения и валидации."""
    dataset = TextDataset(encoded_text, seq_length, stride=stride)
    train_size = int(len(dataset) * train_ratio)
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        dataset, [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True,
                              num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False,
                            num_workers=0, pin_memory=True)
    print(f"[Данные] Обучающая выборка: {train_size} примеров, валидационная: {val_size} примеров")
    return train_loader, val_loader


def train_model(model, train_loader, val_loader, epochs, device, lr=1e-3,
                model_name="model", use_amp=False):
    """Обучение модели с валидацией и ранней остановкой."""
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler('cuda') if use_amp else None

    best_val_loss = float('inf')
    history = {'train_loss': [], 'val_loss': [], 'val_perplexity': []}
    patience = 5
    patience_counter = 0

    print(f"\n{'='*60}")
    print(f"Обучение модели: {model_name}")
    print(f"Параметры: {sum(p.numel() for p in model.parameters()):,}")
    print(f"Устройство: {device}, AMP: {use_amp}")
    print(f"{'='*60}")

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        n_batches = len(train_loader)
        start_time = time.time()

        for batch_idx, (batch_x, batch_y) in enumerate(train_loader):
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimizer.zero_grad()

            if use_amp:
                with torch.amp.autocast('cuda'):
                    logits, _ = model(batch_x)
                    loss = criterion(logits.view(-1, logits.size(-1)), batch_y.view(-1))
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                logits, _ = model(batch_x)
                loss = criterion(logits.view(-1, logits.size(-1)), batch_y.view(-1))
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

            total_loss += loss.item()

            if (batch_idx + 1) % 500 == 0:
                avg_so_far = total_loss / (batch_idx + 1)
                elapsed_so_far = time.time() - start_time
                print(f"    [{batch_idx+1}/{n_batches}] потери: {avg_so_far:.4f} | {elapsed_so_far:.1f}с", flush=True)

        scheduler.step()
        avg_train_loss = total_loss / len(train_loader)
        val_loss = compute_validation_loss(model, val_loader, criterion, device, use_amp)
        val_ppl = np.exp(min(val_loss, 20))
        elapsed = time.time() - start_time

        history['train_loss'].append(avg_train_loss)
        history['val_loss'].append(val_loss)
        history['val_perplexity'].append(val_ppl)

        print(f"  Эпоха {epoch+1:3d}/{epochs} | "
              f"Потери обуч.: {avg_train_loss:.4f} | "
              f"Потери вал.: {val_loss:.4f} | "
              f"Перплексия: {val_ppl:.2f} | "
              f"Время: {elapsed:.1f}с")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            os.makedirs("checkpoints", exist_ok=True)
            torch.save(model.state_dict(), f"checkpoints/{model_name}_best.pt")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"  Ранняя остановка на эпохе {epoch+1}")
                break

    model.load_state_dict(torch.load(f"checkpoints/{model_name}_best.pt", weights_only=True))
    print(f"  Лучшие потери на валидации: {best_val_loss:.4f} (перплексия: {np.exp(min(best_val_loss, 20)):.2f})")
    return history


def compute_validation_loss(model, val_loader, criterion, device, use_amp=False):
    """Вычисляет среднюю функцию потерь на валидационной выборке."""
    model.eval()
    total_loss = 0
    with torch.no_grad():
        for batch_x, batch_y in val_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            if use_amp:
                with torch.amp.autocast('cuda'):
                    logits, _ = model(batch_x)
                    loss = criterion(logits.view(-1, logits.size(-1)), batch_y.view(-1))
            else:
                logits, _ = model(batch_x)
                loss = criterion(logits.view(-1, logits.size(-1)), batch_y.view(-1))
            total_loss += loss.item()
    return total_loss / len(val_loader)


def compute_perplexity(model, dataloader, device, use_amp=False):
    """Вычисляет перплексию модели на заданном наборе данных."""
    criterion = nn.CrossEntropyLoss()
    val_loss = compute_validation_loss(model, dataloader, criterion, device, use_amp)
    return np.exp(min(val_loss, 20))


def generate_text(model, seed_indices, vocab_size, idx_to_token, length=200,
                  temperature=0.8, device='cpu', top_k=40):
    """Генерация текста с temperature и top-k сэмплированием."""
    model.eval()
    generated = list(seed_indices)
    input_seq = torch.tensor([seed_indices], dtype=torch.long).to(device)

    with torch.no_grad():
        for _ in range(length):
            if input_seq.size(1) > 512:
                input_seq = input_seq[:, -512:]

            logits, _ = model(input_seq)
            logits = logits[0, -1, :] / temperature

            if top_k > 0:
                values, indices = torch.topk(logits, top_k)
                logits_filtered = torch.full_like(logits, float('-inf'))
                logits_filtered.scatter_(0, indices, values)
                logits = logits_filtered

            probs = torch.softmax(logits, dim=0)
            next_idx = torch.multinomial(probs, 1).item()
            generated.append(next_idx)
            input_seq = torch.cat([input_seq, torch.tensor([[next_idx]], device=device)], dim=1)

    tokens = [idx_to_token.get(i, '?') for i in generated]
    return tokens


def plot_training_history(histories, model_names):
    """Визуализация графиков обучения."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for name, hist in zip(model_names, histories):
        axes[0].plot(hist['train_loss'], label=f'{name} (обуч.)', linestyle='--')
        axes[0].plot(hist['val_loss'], label=f'{name} (вал.)')

    axes[0].set_xlabel('Эпоха')
    axes[0].set_ylabel('Потери (Cross-Entropy)')
    axes[0].set_title('Функция потерь')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    for name, hist in zip(model_names, histories):
        axes[1].plot(hist['val_perplexity'], label=name)

    axes[1].set_xlabel('Эпоха')
    axes[1].set_ylabel('Перплексия')
    axes[1].set_title('Перплексия на валидации')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('training_curves.png', dpi=150, bbox_inches='tight')
    plt.show()


def print_results_table(results):
    """Выводит сравнительную таблицу результатов."""
    print(f"\n{'='*70}")
    print(f"{'Модель':<30} {'Параметры':>12} {'Вал. потери':>12} {'Перплексия':>12}")
    print(f"{'-'*70}")
    for r in results:
        print(f"{r['name']:<30} {r['params']:>12,} {r['val_loss']:>12.4f} {r['perplexity']:>12.2f}")
    print(f"{'='*70}")
