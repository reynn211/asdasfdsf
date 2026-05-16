#include "analyzer/ngrams.hpp"

namespace analyzer {

std::unordered_map<std::string, int> build_ngrams(
    const std::vector<std::string> &tokens, int n) {
    std::unordered_map<std::string, int> counts;
    if (n < 2 || tokens.size() < static_cast<std::size_t>(n)) {
        return counts;
    }

    const std::size_t end = tokens.size() - static_cast<std::size_t>(n) + 1;
    for (std::size_t i = 0; i < end; ++i) {
        std::string phrase = tokens[i];
        for (int k = 1; k < n; ++k) {
            phrase.push_back(' ');
            phrase.append(tokens[i + k]);
        }
        ++counts[phrase];
    }
    return counts;
}

}  // namespace analyzer
