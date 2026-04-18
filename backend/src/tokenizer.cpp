#include "analyzer/tokenizer.hpp"

#include <cstdint>
#include <string_view>

namespace {

bool next_utf8_codepoint(std::string_view text, std::size_t &pos, std::uint32_t &cp) {
    const unsigned char first = static_cast<unsigned char>(text[pos]);

    if (first < 0x80) {
        cp = first;
        ++pos;
        return true;
    }

    std::size_t len = 0;
    std::uint32_t value = 0;
    std::uint32_t min_value = 0;

    if ((first & 0xE0) == 0xC0) {
        len = 2;
        value = first & 0x1F;
        min_value = 0x80;
    } else if ((first & 0xF0) == 0xE0) {
        len = 3;
        value = first & 0x0F;
        min_value = 0x800;
    } else if ((first & 0xF8) == 0xF0) {
        len = 4;
        value = first & 0x07;
        min_value = 0x10000;
    } else {
        ++pos;
        return false;
    }

    if (pos + len > text.size()) {
        ++pos;
        return false;
    }

    for (std::size_t i = 1; i < len; ++i) {
        const unsigned char byte = static_cast<unsigned char>(text[pos + i]);
        if ((byte & 0xC0) != 0x80) {
            ++pos;
            return false;
        }
        value = (value << 6) | (byte & 0x3F);
    }

    const bool surrogate = value >= 0xD800 && value <= 0xDFFF;
    if (value < min_value || value > 0x10FFFF || surrogate) {
        ++pos;
        return false;
    }

    cp = value;
    pos += len;
    return true;
}

void append_utf8(std::string &out, std::uint32_t cp) {
    if (cp < 0x80) {
        out += static_cast<char>(cp);
    } else if (cp < 0x800) {
        out += static_cast<char>(0xC0 | (cp >> 6));
        out += static_cast<char>(0x80 | (cp & 0x3F));
    } else if (cp < 0x10000) {
        out += static_cast<char>(0xE0 | (cp >> 12));
        out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (cp & 0x3F));
    } else {
        out += static_cast<char>(0xF0 | (cp >> 18));
        out += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
        out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (cp & 0x3F));
    }
}

bool is_ascii_alnum(std::uint32_t cp) {
    return (cp >= '0' && cp <= '9') ||
           (cp >= 'A' && cp <= 'Z') ||
           (cp >= 'a' && cp <= 'z');
}

bool is_cyrillic_letter(std::uint32_t cp) {
    return (cp >= 0x0400 && cp <= 0x0481) ||
           (cp >= 0x048A && cp <= 0x04FF);
}

bool is_hyphen(std::uint32_t cp) {
    return cp == '-' || cp == 0x2010 || cp == 0x2011;
}

std::uint32_t to_lower_codepoint(std::uint32_t cp) {
    if (cp >= 'A' && cp <= 'Z') {
        return cp + ('a' - 'A');
    }

    if (cp >= 0x0410 && cp <= 0x042F) {
        return cp + 0x20;
    }

    if (cp >= 0x0400 && cp <= 0x040F) {
        return cp + 0x50;
    }

    if ((cp >= 0x0460 && cp <= 0x0481 && (cp & 1u) == 0u) ||
        (cp >= 0x048A && cp <= 0x04BF && (cp & 1u) == 0u) ||
        (cp >= 0x04D0 && cp <= 0x04F9 && (cp & 1u) == 0u)) {
        return cp + 1;
    }

    if (cp >= 0x04C1 && cp <= 0x04CE && (cp & 1u) == 1u) {
        return cp + 1;
    }

    if (cp == 0x04C0) {
        return 0x04CF;
    }

    return cp;
}

bool is_token_codepoint(std::uint32_t cp) {
    return is_ascii_alnum(cp) || is_cyrillic_letter(cp);
}

bool next_is_word_start(std::string_view text, std::size_t pos) {
    if (pos >= text.size()) {
        return false;
    }

    std::uint32_t cp = 0;
    if (!next_utf8_codepoint(text, pos, cp)) {
        return false;
    }

    return is_token_codepoint(cp);
}

void append_hyphen(std::string &out, std::uint32_t cp) {
    // Normalize all supported hyphen-like separators to the ASCII hyphen.
    (void)cp;
    out += '-';
}

}  // namespace

namespace analyzer {

std::vector<std::string> tokenize_utf8(std::string_view text, bool keep_internal_hyphen) {
    std::vector<std::string> tokens;
    std::string current;
    std::size_t pos = 0;

    while (pos < text.size()) {
        std::uint32_t cp = 0;
        if (!next_utf8_codepoint(text, pos, cp)) {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
            continue;
        }

        if (is_hyphen(cp) && keep_internal_hyphen) {
            const bool at_token_end = pos >= text.size();
            if (current.empty() || at_token_end || !next_is_word_start(text, pos)) {
                if (!current.empty()) {
                    tokens.push_back(current);
                    current.clear();
                }
                continue;
            }

            append_hyphen(current, cp);
            continue;
        }

        if (!is_token_codepoint(cp)) {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
            continue;
        }

        append_utf8(current, to_lower_codepoint(cp));
    }

    if (!current.empty()) {
        tokens.push_back(current);
    }

    return tokens;
}

}  // namespace analyzer
