#pragma once

#include <string>
#include <string_view>
#include <vector>

namespace analyzer {

struct ReadabilityResult {
    long long words = 0;
    long long sentences = 0;
    long long syllables = 0;
    double avg_word_length = 0.0;     // codepoints per word
    double avg_sentence_length = 0.0; // words per sentence
    double flesch = 0.0;              // Flesch reading-ease (classic formula)
};

// Compute simple readability metrics.
//   `text`     — raw input, used only for sentence boundary counting (.!?).
//   `tokens`   — already-tokenized words from analyzer::tokenize_utf8.
//   `language` — "ru" | "en" | "unknown"; selects the vowel set used for
//                 syllable counting. "unknown" uses the union of both sets.
//
// Returns an all-zero result when `tokens` is empty.
ReadabilityResult compute_readability(std::string_view text,
                                      const std::vector<std::string> &tokens,
                                      std::string_view language);

}  // namespace analyzer
