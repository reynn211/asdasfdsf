#pragma once

#include <string>
#include <string_view>
#include <unordered_set>

namespace analyzer {

// Loads stop words from a UTF-8 file. Lines starting with '#' and blank
// lines are skipped. Tokens are stored verbatim (callers must already pass
// normalized text — same lowercase rules the tokenizer applies).
std::unordered_set<std::string> load_stop_words(const std::string &path);

}  // namespace analyzer
