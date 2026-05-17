#include "analyzer/stemmer.hpp"

#include <cstring>
#include <string>
#include <vector>

// ===========================================================================
// Russian Porter (Snowball) stemmer.
// All Cyrillic letters in the Basic Multilingual Plane are exactly 2 bytes in
// UTF-8 (0xD0/0xD1 lead byte + continuation). We exploit this: byte offsets
// step in increments of 2 across Cyrillic-only words, and suffix comparison
// reduces to plain std::string::compare on UTF-8 byte sequences.
// ===========================================================================

namespace {

// --- Vowel detection -------------------------------------------------------
// Vowels: а е ё и о у ы э ю я. UTF-8 bytes:
//   а D0 B0, е D0 B5, и D0 B8, о D0 BE,
//   ё D1 91, у D1 83, ы D1 8B, э D1 8D, ю D1 8E, я D1 8F.
bool ru_is_vowel_at(std::string_view s, std::size_t p) {
    if (p + 2 > s.size()) return false;
    const auto b0 = static_cast<unsigned char>(s[p]);
    const auto b1 = static_cast<unsigned char>(s[p + 1]);
    if (b0 == 0xD0) {
        return b1 == 0xB0 || b1 == 0xB5 || b1 == 0xB8 || b1 == 0xBE;
    }
    if (b0 == 0xD1) {
        return b1 == 0x91 || b1 == 0x83 || b1 == 0x8B || b1 == 0x8D ||
               b1 == 0x8E || b1 == 0x8F;
    }
    return false;
}

// Byte index of RV: position immediately after the first vowel.
std::size_t find_rv(std::string_view s) {
    for (std::size_t p = 0; p + 2 <= s.size(); p += 2) {
        if (ru_is_vowel_at(s, p)) return p + 2;
    }
    return s.size();
}

// Byte index of R2: applies the Snowball "first non-vowel after first vowel"
// rule twice.
std::size_t find_r2(std::string_view s) {
    std::size_t r1 = s.size();
    bool saw_vowel = false;
    for (std::size_t p = 0; p + 2 <= s.size(); p += 2) {
        const bool v = ru_is_vowel_at(s, p);
        if (saw_vowel && !v) { r1 = p + 2; break; }
        if (v) saw_vowel = true;
    }
    if (r1 >= s.size()) return s.size();

    saw_vowel = false;
    for (std::size_t p = r1; p + 2 <= s.size(); p += 2) {
        const bool v = ru_is_vowel_at(s, p);
        if (saw_vowel && !v) return p + 2;
        if (v) saw_vowel = true;
    }
    return s.size();
}

// Strip the longest matching suffix from `s` provided the match starts at a
// byte index >= region. Returns true if anything was stripped.
bool strip_longest_in_region(
    std::string &s,
    std::size_t region,
    const std::vector<std::string> &suffixes
) {
    std::size_t best = 0;
    for (const auto &suf : suffixes) {
        const std::size_t L = suf.size();
        if (L <= best || s.size() < L) continue;
        const std::size_t pos = s.size() - L;
        if (pos < region) continue;
        if (s.compare(pos, L, suf) == 0) best = L;
    }
    if (best == 0) return false;
    s.resize(s.size() - best);
    return true;
}

// Same as strip_longest_in_region, but the byte immediately preceding the
// stripped suffix must be one of `precedents` (each 2 bytes). Used for the
// Snowball "group 1" suffixes that require а or я before them.
bool strip_longest_after_precedent(
    std::string &s,
    std::size_t region,
    const std::vector<std::string> &suffixes,
    const std::vector<std::string> &precedents
) {
    std::size_t best = 0;
    for (const auto &suf : suffixes) {
        const std::size_t L = suf.size();
        if (L <= best || s.size() < L + 2) continue;
        const std::size_t pos = s.size() - L;
        if (pos < region) continue;
        if (s.compare(pos, L, suf) != 0) continue;
        bool ok = false;
        for (const auto &p : precedents) {
            if (s.compare(pos - 2, 2, p) == 0) { ok = true; break; }
        }
        if (ok) best = L;
    }
    if (best == 0) return false;
    s.resize(s.size() - best);
    return true;
}

// ---- Suffix tables (Snowball Russian) -------------------------------------
const std::vector<std::string> kRuPerfGerundG2 = {
    u8"ившись", u8"ывшись", u8"ивши", u8"ывши", u8"ив", u8"ыв"
};
const std::vector<std::string> kRuPerfGerundG1 = {
    u8"вшись", u8"вши", u8"в"
};
const std::vector<std::string> kRuReflexive = { u8"ся", u8"сь" };
const std::vector<std::string> kRuAdjective = {
    u8"ее", u8"ие", u8"ые", u8"ое", u8"ими", u8"ыми", u8"ей", u8"ий", u8"ый", u8"ой",
    u8"ем", u8"им", u8"ым", u8"ом", u8"его", u8"ого", u8"ему", u8"ому", u8"их", u8"ых",
    u8"ую", u8"юю", u8"ая", u8"яя", u8"ою", u8"ею"
};
const std::vector<std::string> kRuParticipleG2 = { u8"ивш", u8"ывш", u8"ующ" };
const std::vector<std::string> kRuParticipleG1 = { u8"ем", u8"нн", u8"вш", u8"ющ", u8"щ" };
const std::vector<std::string> kRuVerbG2 = {
    u8"ила", u8"ыла", u8"ена", u8"ейте", u8"уйте", u8"ите", u8"или", u8"ыли",
    u8"ей",  u8"уй",  u8"ил",  u8"ыл",   u8"им",   u8"ым",  u8"ен",  u8"ило",
    u8"ыло", u8"ено", u8"ят",  u8"ует",  u8"уют",  u8"ит",  u8"ыт",  u8"ены",
    u8"ить", u8"ыть", u8"ишь", u8"ую",   u8"ю"
};
const std::vector<std::string> kRuVerbG1 = {
    u8"ете", u8"йте", u8"ешь", u8"нно",
    u8"ла",  u8"на",  u8"ли",  u8"ем",  u8"ло", u8"но", u8"ет",
    u8"ют",  u8"ны",  u8"ть",  u8"й",   u8"л",  u8"н"
};
const std::vector<std::string> kRuNoun = {
    u8"иями", u8"ями", u8"ами", u8"ией", u8"иям", u8"ием", u8"иях",
    u8"ев",   u8"ов",  u8"ие",  u8"ье",  u8"еи",  u8"ии",  u8"ей", u8"ой", u8"ий",
    u8"ям",   u8"ем",  u8"ам",  u8"ом",  u8"ах",  u8"ях",  u8"ию", u8"ью",
    u8"ия",   u8"ья",
    u8"а",    u8"е",   u8"и",   u8"й",   u8"о",   u8"у",   u8"ы",  u8"ь",  u8"ю", u8"я"
};
const std::vector<std::string> kRuDeriv      = { u8"ость", u8"ост" };
const std::vector<std::string> kRuSuperl     = { u8"ейше", u8"ейш" };
const std::vector<std::string> kRuPrecAYa    = { u8"а", u8"я" };

}  // namespace

namespace analyzer {

std::string stem_ru(std::string_view input) {
    if (input.empty()) return std::string(input);
    const std::size_t RV = find_rv(input);
    const std::size_t R2 = find_r2(input);
    std::string s(input);

    // Step 1: perfective gerund OR (optional reflexive + adj/verb/noun).
    bool step1_done = false;
    if (strip_longest_in_region(s, RV, kRuPerfGerundG2)) {
        step1_done = true;
    } else if (strip_longest_after_precedent(s, RV, kRuPerfGerundG1, kRuPrecAYa)) {
        step1_done = true;
    }

    if (!step1_done) {
        // Reflexive is optional.
        strip_longest_in_region(s, RV, kRuReflexive);

        // Adjective (possibly followed by participle), or verb, or noun.
        const bool adj = strip_longest_in_region(s, RV, kRuAdjective);
        if (adj) {
            if (!strip_longest_in_region(s, RV, kRuParticipleG2)) {
                strip_longest_after_precedent(s, RV, kRuParticipleG1, kRuPrecAYa);
            }
        } else {
            bool verb = strip_longest_in_region(s, RV, kRuVerbG2);
            if (!verb) {
                verb = strip_longest_after_precedent(s, RV, kRuVerbG1, kRuPrecAYa);
            }
            if (!verb) {
                strip_longest_in_region(s, RV, kRuNoun);
            }
        }
    }

    // Step 2: strip trailing "и" if it sits in RV.
    {
        static const std::string kI = u8"и";
        if (s.size() >= kI.size() && s.size() - kI.size() >= RV &&
            s.compare(s.size() - kI.size(), kI.size(), kI) == 0) {
            s.resize(s.size() - kI.size());
        }
    }

    // Step 3: derivational suffix in R2.
    strip_longest_in_region(s, R2, kRuDeriv);

    // Step 4: нн → н, optional superlative, trailing ь.
    {
        static const std::string kNN = u8"нн";
        static const std::string kN  = u8"н";
        static const std::string kSoft = u8"ь";

        auto ends_with = [&](const std::string &suf) {
            return s.size() >= suf.size() &&
                   s.compare(s.size() - suf.size(), suf.size(), suf) == 0;
        };

        if (ends_with(kNN)) {
            s.resize(s.size() - kN.size());
        } else if (strip_longest_in_region(s, RV, kRuSuperl)) {
            if (ends_with(kNN)) s.resize(s.size() - kN.size());
        }
        if (ends_with(kSoft)) {
            s.resize(s.size() - kSoft.size());
        }
    }

    return s;
}

}  // namespace analyzer


// ===========================================================================
// English Porter (1980) stemmer.
// ===========================================================================

namespace {

bool en_is_vowel_at(const std::string &s, std::size_t i) {
    const char c = s[i];
    if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u') return true;
    if (c == 'y') return i > 0 && !en_is_vowel_at(s, i - 1);
    return false;
}

// Porter's m: count of VC pairs in s[0..end).
int en_measure(const std::string &s, std::size_t end) {
    std::size_t i = 0;
    while (i < end && !en_is_vowel_at(s, i)) ++i;
    int m = 0;
    while (i < end) {
        while (i < end && en_is_vowel_at(s, i)) ++i;
        if (i >= end) break;
        while (i < end && !en_is_vowel_at(s, i)) ++i;
        ++m;
    }
    return m;
}

bool en_has_vowel(const std::string &s, std::size_t end) {
    for (std::size_t i = 0; i < end; ++i) {
        if (en_is_vowel_at(s, i)) return true;
    }
    return false;
}

bool en_ends_double_cons(const std::string &s, std::size_t end) {
    if (end < 2) return false;
    if (s[end - 1] != s[end - 2]) return false;
    return !en_is_vowel_at(s, end - 1);
}

bool en_ends_cvc(const std::string &s, std::size_t end) {
    if (end < 3) return false;
    if (en_is_vowel_at(s, end - 1)) return false;
    if (!en_is_vowel_at(s, end - 2)) return false;
    if (en_is_vowel_at(s, end - 3)) return false;
    const char c = s[end - 1];
    return c != 'w' && c != 'x' && c != 'y';
}

bool en_ends_with(const std::string &s, std::size_t end, const char *suf) {
    const std::size_t L = std::strlen(suf);
    if (end < L) return false;
    return s.compare(end - L, L, suf) == 0;
}

struct EnRule { const char *from; const char *to; };

// Try each (from -> to) rule in order; on the first whose suffix matches and
// whose stem measure is > min_m, apply the replacement and stop. Returns the
// new logical end (== s.size() after potential resize+append).
std::size_t en_apply_rules(
    std::string &s,
    std::size_t end,
    const EnRule *rules,
    std::size_t n,
    int min_m
) {
    for (std::size_t i = 0; i < n; ++i) {
        const auto &r = rules[i];
        if (!en_ends_with(s, end, r.from)) continue;
        const std::size_t stem_end = end - std::strlen(r.from);
        if (en_measure(s, stem_end) <= min_m) return end;
        s.resize(stem_end);
        s.append(r.to);
        return s.size();
    }
    return end;
}

}  // namespace

namespace analyzer {

std::string stem_en(std::string_view input) {
    if (input.size() <= 2) return std::string(input);
    std::string s(input);
    std::size_t end = s.size();

    // Step 1a.
    if (en_ends_with(s, end, "sses")) { s.resize(end - 2); end -= 2; }
    else if (en_ends_with(s, end, "ies")) { s.resize(end - 2); end -= 2; }
    else if (en_ends_with(s, end, "ss")) { /* unchanged */ }
    else if (en_ends_with(s, end, "s"))  { s.resize(end - 1); end -= 1; }

    // Step 1b.
    bool did_1b_replace = false;
    if (en_ends_with(s, end, "eed")) {
        if (en_measure(s, end - 3) > 0) { s.resize(end - 1); end -= 1; }
    } else if (en_ends_with(s, end, "ed") && en_has_vowel(s, end - 2)) {
        s.resize(end - 2); end -= 2;
        did_1b_replace = true;
    } else if (en_ends_with(s, end, "ing") && en_has_vowel(s, end - 3)) {
        s.resize(end - 3); end -= 3;
        did_1b_replace = true;
    }
    if (did_1b_replace) {
        if (en_ends_with(s, end, "at") || en_ends_with(s, end, "bl") || en_ends_with(s, end, "iz")) {
            s.append("e"); end += 1;
        } else if (en_ends_double_cons(s, end) &&
                   s[end - 1] != 'l' && s[end - 1] != 's' && s[end - 1] != 'z') {
            s.resize(end - 1); end -= 1;
        } else if (en_measure(s, end) == 1 && en_ends_cvc(s, end)) {
            s.append("e"); end += 1;
        }
    }

    // Step 1c.
    if (en_ends_with(s, end, "y") && en_has_vowel(s, end - 1)) {
        s[end - 1] = 'i';
    }

    // Step 2.
    static const EnRule step2[] = {
        {"ational", "ate"}, {"tional", "tion"}, {"enci", "ence"}, {"anci", "ance"},
        {"izer", "ize"},    {"abli", "able"},   {"alli", "al"},    {"entli", "ent"},
        {"eli", "e"},       {"ousli", "ous"},   {"ization", "ize"},{"ation", "ate"},
        {"ator", "ate"},    {"alism", "al"},    {"iveness", "ive"},{"fulness", "ful"},
        {"ousness", "ous"}, {"aliti", "al"},    {"iviti", "ive"},  {"biliti", "ble"}
    };
    end = en_apply_rules(s, end, step2, sizeof(step2) / sizeof(step2[0]), 0);

    // Step 3.
    static const EnRule step3[] = {
        {"icate", "ic"}, {"ative", ""}, {"alize", "al"}, {"iciti", "ic"},
        {"ical", "ic"},  {"ful", ""},   {"ness", ""}
    };
    end = en_apply_rules(s, end, step3, sizeof(step3) / sizeof(step3[0]), 0);

    // Step 4.
    static const char *step4[] = {
        "al", "ance", "ence", "er", "ic", "able", "ible", "ant", "ement",
        "ment", "ent", "ou", "ism", "ate", "iti", "ous", "ive", "ize"
    };
    bool s4 = false;
    for (auto *suf : step4) {
        const std::size_t fl = std::strlen(suf);
        if (en_ends_with(s, end, suf)) {
            if (en_measure(s, end - fl) > 1) {
                s.resize(end - fl);
                end -= fl;
            }
            s4 = true;
            break;
        }
    }
    if (!s4 && en_ends_with(s, end, "ion")) {
        if (end >= 4 && (s[end - 4] == 's' || s[end - 4] == 't') &&
            en_measure(s, end - 3) > 1) {
            s.resize(end - 3); end -= 3;
        }
    }

    // Step 5a.
    if (en_ends_with(s, end, "e")) {
        const int m = en_measure(s, end - 1);
        if (m > 1 || (m == 1 && !en_ends_cvc(s, end - 1))) {
            s.resize(end - 1); end -= 1;
        }
    }

    // Step 5b.
    if (en_ends_with(s, end, "ll") && en_measure(s, end) > 1) {
        s.resize(end - 1);
    }

    return s;
}

}  // namespace analyzer


// ===========================================================================
// Dispatcher.
// ===========================================================================

namespace {

bool is_all_ascii_letters(std::string_view s) {
    if (s.empty()) return false;
    for (char c : s) {
        const unsigned char u = static_cast<unsigned char>(c);
        if (!((u >= 'a' && u <= 'z') || (u >= 'A' && u <= 'Z'))) return false;
    }
    return true;
}

bool is_all_cyrillic(std::string_view s) {
    if (s.empty() || (s.size() % 2) != 0) return false;
    for (std::size_t i = 0; i + 2 <= s.size(); i += 2) {
        const auto b0 = static_cast<unsigned char>(s[i]);
        const auto b1 = static_cast<unsigned char>(s[i + 1]);
        // Cyrillic block (U+0400..U+04FF) encodes as 0xD0 0x80..BF or 0xD1 0x80..BF.
        if (!((b0 == 0xD0 || b0 == 0xD1) && b1 >= 0x80 && b1 <= 0xBF)) return false;
    }
    return true;
}

}  // namespace

namespace analyzer {

std::string stem_token(std::string_view word) {
    if (is_all_cyrillic(word)) return stem_ru(word);
    if (is_all_ascii_letters(word)) return stem_en(word);
    return std::string(word);
}

}  // namespace analyzer
