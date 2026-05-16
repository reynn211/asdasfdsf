#pragma once

#include <string>
#include <unordered_map>
#include <vector>

namespace analyzer {

// Build an n-gram frequency map from a token sequence. Phrases are joined by
// a single ASCII space. Returns an empty map if n < 2 or tokens.size() < n.
std::unordered_map<std::string, int> build_ngrams(
    const std::vector<std::string> &tokens, int n);

}  // namespace analyzer
