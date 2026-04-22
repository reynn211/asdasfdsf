#include "analyzer/stop_words.hpp"

#include <fstream>
#include <sstream>

namespace analyzer {

std::unordered_set<std::string> load_stop_words(const std::string &path) {
    std::unordered_set<std::string> result;
    std::ifstream file(path);
    if (!file.is_open()) {
        return result;
    }

    std::string line;
    while (std::getline(file, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ' || line.back() == '\t')) {
            line.pop_back();
        }
        std::size_t start = 0;
        while (start < line.size() && (line[start] == ' ' || line[start] == '\t')) {
            ++start;
        }
        if (start >= line.size() || line[start] == '#') {
            continue;
        }
        result.emplace(line.substr(start));
    }

    return result;
}

}  // namespace analyzer
