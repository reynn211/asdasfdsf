
"""
Утилиты для работы с MIDI-файлами.
Токенизация MIDI-событий в последовательности для обучения нейросетей.
"""
import os
import glob
from typing import List, Tuple

try:
    import mido
except ImportError:
    raise ImportError("Установите mido: pip install mido")


# === Схема токенизации ===
# NOTE_ON_0..127   (128 токенов) — нажатие ноты
# NOTE_OFF_0..127  (128 токенов) — отпускание ноты
# TIME_SHIFT_1..100 (100 токенов) — сдвиг времени (×10мс, макс 1000мс)
# VELOCITY_0..31   (32 токена) — громкость (квантованная)

NUM_PITCHES = 128
NUM_TIME_SHIFTS = 100
NUM_VELOCITIES = 32
TIME_SHIFT_MS = 10  # один шаг = 10мс

# Границы индексов
NOTE_ON_OFFSET = 0
NOTE_OFF_OFFSET = NUM_PITCHES
TIME_SHIFT_OFFSET = NOTE_OFF_OFFSET + NUM_PITCHES
VELOCITY_OFFSET = TIME_SHIFT_OFFSET + NUM_TIME_SHIFTS

VOCAB_SIZE = VELOCITY_OFFSET + NUM_VELOCITIES  # 388

# Имена токенов для отображения
def token_to_str(token_id: int) -> str:
    if token_id < NOTE_OFF_OFFSET:
        return f"NOTE_ON_{token_id}"
    elif token_id < TIME_SHIFT_OFFSET:
        return f"NOTE_OFF_{token_id - NOTE_OFF_OFFSET}"
    elif token_id < VELOCITY_OFFSET:
        return f"TIME_SHIFT_{(token_id - TIME_SHIFT_OFFSET + 1) * TIME_SHIFT_MS}ms"
    else:
        return f"VELOCITY_{token_id - VELOCITY_OFFSET}"


def midi_to_tokens(midi_path: str) -> List[int]:
    """Конвертирует MIDI-файл в последовательность токенов."""
    mid = mido.MidiFile(midi_path)
    events = []

    for track in mid.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                events.append((abs_time, 'note_on', msg.note, msg.velocity))
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                events.append((abs_time, 'note_off', msg.note, 0))

    # Сортируем по времени
    events.sort(key=lambda x: x[0])

    # Конвертируем в токены
    tokens = []
    prev_time = 0
    prev_velocity = -1

    ticks_per_beat = mid.ticks_per_beat if mid.ticks_per_beat else 480
    # Находим темп (по умолчанию 120 BPM)
    tempo = 500000  # микросекунды на бит (120 BPM)
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                tempo = msg.tempo
                break

    for abs_time, event_type, pitch, velocity in events:
        # Вычисляем временной сдвиг в миллисекундах
        delta_ticks = abs_time - prev_time
        delta_ms = int(mido.tick2second(delta_ticks, ticks_per_beat, tempo) * 1000)

        # Кодируем временной сдвиг (несколькими токенами если нужно)
        while delta_ms > 0:
            shift = min(delta_ms, NUM_TIME_SHIFTS * TIME_SHIFT_MS)
            shift_steps = max(1, shift // TIME_SHIFT_MS)
            tokens.append(TIME_SHIFT_OFFSET + shift_steps - 1)
            delta_ms -= shift_steps * TIME_SHIFT_MS

        prev_time = abs_time

        if event_type == 'note_on':
            # Кодируем громкость (если изменилась)
            vel_bucket = min(velocity // 4, NUM_VELOCITIES - 1)
            if vel_bucket != prev_velocity:
                tokens.append(VELOCITY_OFFSET + vel_bucket)
                prev_velocity = vel_bucket
            tokens.append(NOTE_ON_OFFSET + pitch)
        else:
            tokens.append(NOTE_OFF_OFFSET + pitch)

    return tokens


def tokens_to_midi(tokens: List[int], output_path: str, tempo: int = 500000):
    """Конвертирует последовательность токенов обратно в MIDI-файл."""
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    ticks_per_beat = 480
    mid.ticks_per_beat = ticks_per_beat

    track.append(mido.MetaMessage('set_tempo', tempo=tempo))

    current_velocity = 80
    accumulated_time_ms = 0

    for token_id in tokens:
        if token_id < NOTE_OFF_OFFSET:
            # NOTE_ON
            pitch = token_id
            delta_ticks = int(mido.second2tick(
                accumulated_time_ms / 1000.0, ticks_per_beat, tempo))
            track.append(mido.Message('note_on', note=pitch,
                                       velocity=current_velocity, time=delta_ticks))
            accumulated_time_ms = 0

        elif token_id < TIME_SHIFT_OFFSET:
            # NOTE_OFF
            pitch = token_id - NOTE_OFF_OFFSET
            delta_ticks = int(mido.second2tick(
                accumulated_time_ms / 1000.0, ticks_per_beat, tempo))
            track.append(mido.Message('note_off', note=pitch,
                                       velocity=0, time=delta_ticks))
            accumulated_time_ms = 0

        elif token_id < VELOCITY_OFFSET:
            # TIME_SHIFT
            shift_steps = token_id - TIME_SHIFT_OFFSET + 1
            accumulated_time_ms += shift_steps * TIME_SHIFT_MS

        else:
            # VELOCITY
            vel_bucket = token_id - VELOCITY_OFFSET
            current_velocity = min(127, vel_bucket * 4 + 2)

    mid.save(output_path)
    return output_path


def load_midi_dataset(midi_dir: str, max_files: int = None) -> List[int]:
    """Загружает все MIDI-файлы из директории и объединяет в одну последовательность."""
    midi_files = glob.glob(os.path.join(midi_dir, "**/*.mid"), recursive=True)
    midi_files += glob.glob(os.path.join(midi_dir, "**/*.midi"), recursive=True)

    if not midi_files:
        raise FileNotFoundError(
            f"MIDI-файлы не найдены в '{midi_dir}'.\n"
            f"Скачайте датасет, например:\n"
            f"  - MAESTRO: https://magenta.tensorflow.org/datasets/maestro\n"
            f"  - Classical Piano MIDI: https://www.midiworld.com/classic.htm\n"
            f"Поместите .mid файлы в директорию '{midi_dir}'"
        )

    if max_files:
        midi_files = midi_files[:max_files]

    print(f"[MIDI] Найдено {len(midi_files)} файлов")

    all_tokens = []
    errors = 0
    for i, path in enumerate(midi_files):
        try:
            tokens = midi_to_tokens(path)
            if len(tokens) > 100:  # пропускаем слишком короткие
                all_tokens.extend(tokens)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  [!] Ошибка в {os.path.basename(path)}: {e}")

    print(f"[MIDI] Обработано: {len(midi_files) - errors} файлов, "
          f"ошибок: {errors}")
    print(f"[MIDI] Общая длина последовательности: {len(all_tokens):,} токенов")
    print(f"[MIDI] Размер словаря: {VOCAB_SIZE}")

    return all_tokens


def print_token_stats(tokens: List[int]):
    """Выводит статистику по типам токенов."""
    note_on = sum(1 for t in tokens if t < NOTE_OFF_OFFSET)
    note_off = sum(1 for t in tokens if NOTE_OFF_OFFSET <= t < TIME_SHIFT_OFFSET)
    time_shift = sum(1 for t in tokens if TIME_SHIFT_OFFSET <= t < VELOCITY_OFFSET)
    velocity = sum(1 for t in tokens if t >= VELOCITY_OFFSET)

    total = len(tokens)
    print(f"\nСтатистика токенов:")
    print(f"  NOTE_ON:    {note_on:>8,} ({note_on/total*100:.1f}%)")
    print(f"  NOTE_OFF:   {note_off:>8,} ({note_off/total*100:.1f}%)")
    print(f"  TIME_SHIFT: {time_shift:>8,} ({time_shift/total*100:.1f}%)")
    print(f"  VELOCITY:   {velocity:>8,} ({velocity/total*100:.1f}%)")
    print(f"  Всего:      {total:>8,}")
