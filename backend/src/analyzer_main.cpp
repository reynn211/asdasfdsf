#include "analyzer/stop_words.hpp"
#include "analyzer/tokenizer.hpp"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

std::string escape_json(const std::string &s) {
    std::string out;
    for (char c : s) {
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else out += c;
    }
    return out;
}

struct Args {
    std::string input_path;
    bool ignore_stopwords = false;
    std::string stopwords_path;
};

bool parse_args(int argc, char *argv[], Args &out) {
    for (int i = 1; i < argc; ++i) {
        std::string_view arg = argv[i];
        if (arg == "--ignore-stopwords") {
            out.ignore_stopwords = true;
        } else if (arg == "--stopwords-file") {
            if (i + 1 >= argc) return false;
            out.stopwords_path = argv[++i];
        } else if (!arg.empty() && arg[0] == '-') {
            return false;
        } else if (out.input_path.empty()) {
            out.input_path.assign(arg);
        } else {
            return false;
        }
    }
    return !out.input_path.empty();
}

int main(int argc, char *argv[]) {
    Args args;
    if (!parse_args(argc, argv, args)) {
        std::cerr << "Usage: analyzer [--ignore-stopwords] [--stopwords-file <path>] <file.txt>"
                  << std::endl;
        return 1;
    }

    std::ifstream file(args.input_path, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "Cannot open file: " << args.input_path << std::endl;
        return 1;
    }

    const std::string text((std::istreambuf_iterator<char>(file)),
                           std::istreambuf_iterator<char>());

    std::unordered_set<std::string> stop_words;
    if (args.ignore_stopwords && !args.stopwords_path.empty()) {
        stop_words = analyzer::load_stop_words(args.stopwords_path);
    }

    std::unordered_map<std::string, int> freq;
    int total = 0;
    const std::vector<std::string> tokens = analyzer::tokenize_utf8(text);
    for (const auto &token : tokens) {
        total++;
        if (args.ignore_stopwords && stop_words.count(token)) {
            continue;
        }
        freq[token]++;
    }

    std::vector<std::pair<std::string, int>> sorted(freq.begin(), freq.end());
    std::sort(sorted.begin(), sorted.end(),
              [](const auto &a, const auto &b) { return b.second < a.second; });

    std::cout << "{\"total_words\":" << total
              << ",\"unique_words\":" << freq.size()
              << ",\"frequencies\":{";

    for (size_t i = 0; i < sorted.size(); i++) {
        if (i > 0) std::cout << ',';
        std::cout << '"' << escape_json(sorted[i].first) << "\":" << sorted[i].second;
    }

    std::cout << "}}" << std::endl;
    return 0;
}
