#pragma once

#include <string>
#include <string_view>

namespace analyzer {

// Snowball-style Russian Porter stemmer. Input must be a lowercase UTF-8
// string of Cyrillic letters; behaviour on other input is undefined.
std::string stem_ru(std::string_view word);

// Porter 1980 English stemmer. Input must be lowercase ASCII letters.
std::string stem_en(std::string_view word);

// Convenience dispatcher: routes all-Cyrillic tokens to stem_ru, all-ASCII-
// letter tokens to stem_en, and returns anything else unchanged (numbers,
// mixed-script tokens, etc.).
std::string stem_token(std::string_view word);

}  // namespace analyzer
