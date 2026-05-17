import os
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torch.cuda.amp import autocast, GradScaler
from tqdm import tqdm


def load_medium_articles(data_path="data/medium_articles.csv", max_articles=50000):
    """Загружает датасет статей Medium из CSV. Возвращает одну объединённую строку."""
    import pandas as pd

    if not os.path.exists(data_path):
        raise FileNotFoundError(
            f"{data_path} не найден. Скачайте с Kaggle:\n"
            "  kaggle datasets download -d fabiochiusano/medium-articles\n"
            "затем распакуйте в data/"
        )

    df = pd.read_csv(data_path, usecols=["text"], nrows=max_articles)
    df = df.dropna(subset=["text"])
    corpus = "\n\n".join(df["text"].tolist())
    print(f"Загружено {len(df)} статей, длина корпуса: {len(corpus):,} символов")
    return corpus


class TextDataset(Dataset):
    """Универсальный датасет последовательностей — работает с любым токенизатором, возвращающим список int."""

    def __init__(self, token_ids, seq_len):
        self.token_ids = token_ids
        self.seq_len = seq_len
        # общее количество пригодных последовательностей (без перекрытия для простоты)
        self.n_sequences = (len(token_ids) - 1) // seq_len

    def __len__(self):
        return self.n_sequences

    def __getitem__(self, idx):
        start = idx * self.seq_len
        x = self.token_ids[start : start + self.seq_len]
        y = self.token_ids[start + 1 : start + self.seq_len + 1]
        return torch.tensor(x, dtype=torch.long), torch.tensor(y, dtype=torch.long)


def make_dataloaders(token_ids, seq_len, batch_size, val_split=0.1):
    """Разделяет token_ids на train/val и возвращает DataLoader'ы."""
    split = int(len(token_ids) * (1 - val_split))
    train_ds = TextDataset(token_ids[:split], seq_len)
    val_ds = TextDataset(token_ids[split:], seq_len)
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=True)
    val_dl = DataLoader(val_ds, batch_size=batch_size, shuffle=False, drop_last=True)
    print(f"Последовательностей — train: {len(train_ds)}, val: {len(val_ds)}")
    return train_dl, val_dl


def train_model(
    model,
    train_dl,
    val_dl,
    epochs=20,
    lr=1e-3,
    device="cuda",
    use_amp=False,
    patience=5,
    model_name="model",
    save_dir="checkpoints",
):
    """Обучает языковую модель и возвращает словарь с историей метрик."""
    os.makedirs(save_dir, exist_ok=True)
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    scaler = GradScaler(enabled=use_amp)
    criterion = nn.CrossEntropyLoss()

    history = {"train_loss": [], "val_loss": [], "val_ppl": []}
    best_val_loss = float("inf")
    no_improve = 0

    for epoch in range(1, epochs + 1):
        # --- обучение ---
        model.train()
        total_loss, n_batches = 0.0, 0
        for x, y in tqdm(train_dl, desc=f"[{model_name}] Эпоха {epoch}/{epochs}", leave=False):
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            with autocast(enabled=use_amp):
                logits = model(x)  # (B, T, vocab)
                loss = criterion(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            total_loss += loss.item()
            n_batches += 1

        avg_train = total_loss / max(n_batches, 1)
        history["train_loss"].append(avg_train)

        # --- валидация ---
        val_loss = evaluate_loss(model, val_dl, criterion, device, use_amp)
        val_ppl = math.exp(min(val_loss, 20))  # ограничение во избежание переполнения
        history["val_loss"].append(val_loss)
        history["val_ppl"].append(val_ppl)

        print(f"  [{model_name}] Эпоха {epoch}: train_loss={avg_train:.4f}  val_loss={val_loss:.4f}  val_ppl={val_ppl:.2f}")

        # --- чекпоинт / ранняя остановка ---
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            no_improve = 0
            torch.save(model.state_dict(), os.path.join(save_dir, f"{model_name}_best.pt"))
        else:
            no_improve += 1
            if no_improve >= patience:
                print(f"  [{model_name}] Ранняя остановка на эпохе {epoch}")
                break

    # загрузка лучших весов
    model.load_state_dict(torch.load(os.path.join(save_dir, f"{model_name}_best.pt"), map_location=device))
    return history


@torch.no_grad()
def evaluate_loss(model, dataloader, criterion, device="cuda", use_amp=False):
    model.eval()
    total, n = 0.0, 0
    for x, y in dataloader:
        x, y = x.to(device), y.to(device)
        with autocast(enabled=use_amp):
            logits = model(x)
            loss = criterion(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
        total += loss.item()
        n += 1
    return total / max(n, 1)


@torch.no_grad()
def compute_perplexity(model, dataloader, device="cuda", use_amp=False):
    """Вычисляет перплексию на заданном DataLoader."""
    model.eval()
    criterion = nn.CrossEntropyLoss()
    avg_loss = evaluate_loss(model, dataloader, criterion, device, use_amp)
    return math.exp(min(avg_loss, 20))


@torch.no_grad()
def generate_text(model, seed_ids, decode_fn, length=200, temperature=0.8, top_k=40, device="cuda", max_context=512):
    """Авторегрессионная генерация текста с top-k сэмплированием.

    Аргументы:
        model: языковая модель, возвращающая логиты размерности (B, T, vocab).
        seed_ids: list[int] — начальные токены для затравки модели.
        decode_fn: callable(list[int]) -> str — преобразует id обратно в текст.
        length: количество новых токенов для генерации.
        temperature: температура сэмплирования.
        top_k: оставить только top-k логитов перед сэмплированием.
        device: устройство torch.
        max_context: максимальное контекстное окно, подаваемое модели (скользящее окно).
    """
    model.eval()
    generated = list(seed_ids)
    context = torch.tensor([generated[-max_context:]], dtype=torch.long, device=device)

    for _ in range(length):
        logits = model(context)  # (1, T, vocab)
        next_logits = logits[0, -1, :] / temperature

        # top-k фильтрация
        if top_k > 0:
            values, _ = torch.topk(next_logits, top_k)
            next_logits[next_logits < values[-1]] = -float("inf")

        probs = F.softmax(next_logits, dim=-1)
        next_id = torch.multinomial(probs, 1).item()
        generated.append(next_id)

        context = torch.cat([context, torch.tensor([[next_id]], device=device)], dim=1)
        if context.size(1) > max_context:
            context = context[:, -max_context:]

    return decode_fn(generated)


def plot_training_curves(histories, title="Кривые обучения"):
    """Строит графики train/val loss и val perplexity для нескольких моделей.

    Аргументы:
        histories: dict[str, dict] — {имя_модели: {"train_loss": [...], "val_loss": [...], "val_ppl": [...]}}
    """
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    for name, h in histories.items():
        axes[0].plot(h["train_loss"], label=name)
        axes[1].plot(h["val_loss"], label=name)
        axes[2].plot(h["val_ppl"], label=name)

    axes[0].set_title("Train Loss")
    axes[1].set_title("Val Loss")
    axes[2].set_title("Val Perplexity")
    for ax in axes:
        ax.legend()
        ax.set_xlabel("Epoch")
        ax.grid(True, alpha=0.3)

    fig.suptitle(title, fontsize=14)
    plt.tight_layout()
    plt.show()


def print_generation_samples(samples, title="Примеры генерации"):
    """Красиво выводит примеры сгенерированного текста из словаря {имя_модели: текст}."""
    print(f"\n{title}")
    for name, text in samples.items():
        print(f"\n--- {name} ---")
        print(text[:500])
        print()
