#pragma once

#include <string>
#include <string_view>
#include <vector>

namespace analyzer {

// Detect the dominant script in a token stream. Counts letter codepoints
// per script (digits inside tokens are ignored) and returns:
//   "ru"      — Cyrillic letters dominate
//   "en"      — ASCII letters dominate
//   "unknown" — no letters at all (e.g. numbers-only or empty input)
std::string detect_language(const std::vector<std::string> &tokens);

}  // namespace analyzer
