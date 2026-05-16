import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class SimpleRNNModel(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, num_layers=1, dropout=0.1):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.rnn = nn.RNN(embed_dim, hidden_dim, num_layers=num_layers,
                          batch_first=True, dropout=dropout if num_layers > 1 else 0.0)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim, vocab_size)

    def forward(self, x, hidden=None):
        emb = self.dropout(self.embedding(x))
        out, _ = self.rnn(emb, hidden)
        return self.fc(self.dropout(out))


class LSTMModel(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, num_layers=1,
                 bidirectional=False, dropout=0.1):
        super().__init__()
        self.bidirectional = bidirectional
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, num_layers=num_layers,
                            batch_first=True, bidirectional=bidirectional,
                            dropout=dropout if num_layers > 1 else 0.0)
        self.dropout = nn.Dropout(dropout)
        fc_input = hidden_dim * 2 if bidirectional else hidden_dim
        self.fc = nn.Linear(fc_input, vocab_size)

    def forward(self, x, hidden=None):
        emb = self.dropout(self.embedding(x))
        out, _ = self.lstm(emb, hidden)
        return self.fc(self.dropout(out))


class CausalSelfAttention(nn.Module):
    def __init__(self, d_model, n_heads, max_seq_len, dropout=0.1):
        super().__init__()
        assert d_model % n_heads == 0
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.qkv = nn.Linear(d_model, 3 * d_model)
        self.proj = nn.Linear(d_model, d_model)
        self.attn_drop = nn.Dropout(dropout)
        self.proj_drop = nn.Dropout(dropout)
        self.register_buffer("mask", torch.tril(torch.ones(max_seq_len, max_seq_len))
                             .unsqueeze(0).unsqueeze(0))  # (1, 1, T, T)

    def forward(self, x):
        B, T, C = x.size()
        q, k, v = self.qkv(x).split(C, dim=-1)
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)

        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        att = att.masked_fill(self.mask[:, :, :T, :T] == 0, float("-inf"))
        att = self.attn_drop(F.softmax(att, dim=-1))
        out = (att @ v).transpose(1, 2).contiguous().view(B, T, C)
        return self.proj_drop(self.proj(out))


class TransformerBlock(nn.Module):
    def __init__(self, d_model, n_heads, max_seq_len, ff_dim, dropout=0.1):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_heads, max_seq_len, dropout)
        self.ln2 = nn.LayerNorm(d_model)
        self.ff = nn.Sequential(
            nn.Linear(d_model, ff_dim),
            nn.GELU(),
            nn.Linear(ff_dim, d_model),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        x = x + self.ff(self.ln2(x))
        return x


class MiniGPT(nn.Module):
    def __init__(self, vocab_size, d_model=256, n_heads=4, n_layers=4,
                 ff_dim=512, max_seq_len=512, dropout=0.1):
        super().__init__()
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.drop = nn.Dropout(dropout)
        self.blocks = nn.Sequential(
            *[TransformerBlock(d_model, n_heads, max_seq_len, ff_dim, dropout)
              for _ in range(n_layers)]
        )
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)
        # привязка весов
        self.head.weight = self.token_emb.weight
        self.max_seq_len = max_seq_len
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0.0, 0.02)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Embedding):
                nn.init.normal_(m.weight, 0.0, 0.02)

    def forward(self, x):
        B, T = x.size()
        assert T <= self.max_seq_len, f"Длина последовательности {T} превышает максимум {self.max_seq_len}"
        pos = torch.arange(T, device=x.device).unsqueeze(0)
        x = self.drop(self.token_emb(x) + self.pos_emb(pos))
        x = self.blocks(x)
        return self.head(self.ln_f(x))


def build_all_models(vocab_size, embed_dim=128, hidden_dim=256, gpt_dim=256,
                     gpt_heads=4, gpt_layers=4, gpt_ff=512, max_seq_len=512):
    """Создаёт все пять вариантов моделей и возвращает их в виде словаря."""
    return {
        "SimpleRNN": SimpleRNNModel(vocab_size, embed_dim, hidden_dim),
        "LSTM_1layer": LSTMModel(vocab_size, embed_dim, hidden_dim, num_layers=1),
        "LSTM_3layer": LSTMModel(vocab_size, embed_dim, hidden_dim, num_layers=3, dropout=0.2),
        "BiLSTM": LSTMModel(vocab_size, embed_dim, hidden_dim, num_layers=2,
                            bidirectional=True, dropout=0.2),
        "MiniGPT": MiniGPT(vocab_size, d_model=gpt_dim, n_heads=gpt_heads,
                           n_layers=gpt_layers, ff_dim=gpt_ff, max_seq_len=max_seq_len),
    }


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
