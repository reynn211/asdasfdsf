#include "analyzer/readability.hpp"

#include <cctype>
#include <cstdint>

namespace {

bool next_utf8_codepoint(std::string_view text, std::size_t &pos, std::uint32_t &cp) {
    const unsigned char first = static_cast<unsigned char>(text[pos]);
    if (first < 0x80) { cp = first; ++pos; return true; }

    std::size_t len = 0;
    std::uint32_t value = 0;
    if ((first & 0xE0) == 0xC0) { len = 2; value = first & 0x1F; }
    else if ((first & 0xF0) == 0xE0) { len = 3; value = first & 0x0F; }
    else if ((first & 0xF8) == 0xF0) { len = 4; value = first & 0x07; }
    else { ++pos; return false; }

    if (pos + len > text.size()) { ++pos; return false; }
    for (std::size_t i = 1; i < len; ++i) {
        const unsigned char byte = static_cast<unsigned char>(text[pos + i]);
        if ((byte & 0xC0) != 0x80) { ++pos; return false; }
        value = (value << 6) | (byte & 0x3F);
    }
    cp = value;
    pos += len;
    return true;
}

std::size_t codepoint_count(std::string_view s) {
    std::size_t n = 0;
    for (unsigned char b : s) {
        if ((b & 0xC0) != 0x80) ++n;
    }
    return n;
}

bool is_en_vowel(std::uint32_t cp) {
    return cp == 'a' || cp == 'e' || cp == 'i' || cp == 'o' || cp == 'u' || cp == 'y';
}

bool is_ru_vowel(std::uint32_t cp) {
    return cp == 0x0430 /*а*/ || cp == 0x0435 /*е*/ || cp == 0x0451 /*ё*/ ||
           cp == 0x0438 /*и*/ || cp == 0x043E /*о*/ || cp == 0x0443 /*у*/ ||
           cp == 0x044B /*ы*/ || cp == 0x044D /*э*/ || cp == 0x044E /*ю*/ ||
           cp == 0x044F /*я*/;
}

// Count syllables in a single token as the number of vowel groups
// (transitions from non-vowel to vowel). Words with at least one letter
// but no vowels in the chosen set count as one syllable, matching the
// usual Flesch convention.
long long syllables_in(std::string_view word, std::string_view language) {
    const bool use_en = language != "ru";   // "en" or "unknown" → include latin vowels
    const bool use_ru = language != "en";   // "ru" or "unknown" → include cyrillic vowels

    long long groups = 0;
    bool prev_vowel = false;
    bool saw_letter = false;
    std::size_t pos = 0;
    while (pos < word.size()) {
        std::uint32_t cp = 0;
        if (!next_utf8_codepoint(word, pos, cp)) continue;
        const bool letter = (cp >= 'a' && cp <= 'z') ||
                            (cp >= 0x0400 && cp <= 0x04FF);
        if (letter) saw_letter = true;
        const bool vowel = (use_en && is_en_vowel(cp)) || (use_ru && is_ru_vowel(cp));
        if (vowel && !prev_vowel) ++groups;
        prev_vowel = vowel;
    }
    if (saw_letter && groups == 0) groups = 1;
    return groups;
}

long long count_sentences(std::string_view text) {
    long long n = 0;
    bool in_terminator = false;
    bool content_since_last = false;
    for (char c : text) {
        if (c == '.' || c == '!' || c == '?') {
            if (!in_terminator && content_since_last) {
                ++n;
                content_since_last = false;
            }
            in_terminator = true;
        } else {
            in_terminator = false;
            if (!std::isspace(static_cast<unsigned char>(c))) {
                content_since_last = true;
            }
        }
    }
    if (content_since_last) ++n;  // unterminated final sentence
    return n;
}

}  // namespace

namespace analyzer {

ReadabilityResult compute_readability(std::string_view text,
                                      const std::vector<std::string> &tokens,
                                      std::string_view language) {
    ReadabilityResult r;
    if (tokens.empty()) return r;

    long long total_chars = 0;
    long long total_syll = 0;
    for (const auto &tok : tokens) {
        total_chars += static_cast<long long>(codepoint_count(tok));
        total_syll += syllables_in(tok, language);
    }

    r.words = static_cast<long long>(tokens.size());
    r.sentences = count_sentences(text);
    if (r.sentences == 0) r.sentences = 1;  // guard divide-by-zero
    r.syllables = total_syll;

    r.avg_word_length = static_cast<double>(total_chars) / static_cast<double>(r.words);
    r.avg_sentence_length =
        static_cast<double>(r.words) / static_cast<double>(r.sentences);
    r.flesch = 206.835
             - 1.015 * r.avg_sentence_length
             - 84.6 * (static_cast<double>(total_syll) / static_cast<double>(r.words));
    return r;
}

}  // namespace analyzer
