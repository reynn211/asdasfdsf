#include "analyzer/language.hpp"

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

bool is_latin_letter(std::uint32_t cp) {
    return (cp >= 'a' && cp <= 'z') || (cp >= 'A' && cp <= 'Z');
}

bool is_cyrillic_letter(std::uint32_t cp) {
    return (cp >= 0x0400 && cp <= 0x0481) ||
           (cp >= 0x048A && cp <= 0x04FF);
}

}  // namespace

namespace analyzer {

std::string detect_language(const std::vector<std::string> &tokens) {
    long long cyr = 0;
    long long lat = 0;
    for (const auto &tok : tokens) {
        std::size_t pos = 0;
        while (pos < tok.size()) {
            std::uint32_t cp = 0;
            if (!next_utf8_codepoint(tok, pos, cp)) continue;
            if (is_cyrillic_letter(cp)) ++cyr;
            else if (is_latin_letter(cp)) ++lat;
        }
    }
    if (cyr == 0 && lat == 0) return "unknown";
    return cyr >= lat ? "ru" : "en";
}

}  // namespace analyzer
