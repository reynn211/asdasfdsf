#include "analyzer/json_writer.hpp"
#include "analyzer/language.hpp"
#include "analyzer/ngrams.hpp"
#include "analyzer/readability.hpp"
#include "analyzer/stemmer.hpp"
#include "analyzer/stop_words.hpp"
#include "analyzer/tokenizer.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace {

struct Args {
    std::string input_path;
    std::string stopwords_arg;   // "ru" | "en" | <path> | empty
    int ngram = 1;               // 1 = unigrams only; 2/3 = also emit n-grams section
    bool normalize_stem = false;
};

void print_usage(std::ostream &os) {
    os << "Usage: analyzer [options] <file>\n"
       << "  --stopwords <ru|en|path>   Filter stop words. ru/en resolve to bundled lists\n"
       << "                             under <exe>/data/stop_words_<lang>.txt; anything\n"
       << "                             else is treated as a path.\n"
       << "  --ngram <1|2|3>            Also emit an n-grams section (N>=2).\n"
       << "  --normalize <none|stem>    Apply Porter stemming (RU+EN, per-token routing).\n";
}

bool parse_args(int argc, char *argv[], Args &out) {
    for (int i = 1; i < argc; ++i) {
        const std::string_view arg = argv[i];
        if (arg == "--stopwords") {
            if (i + 1 >= argc) return false;
            out.stopwords_arg = argv[++i];
        } else if (arg == "--ngram") {
            if (i + 1 >= argc) return false;
            try {
                out.ngram = std::stoi(argv[++i]);
            } catch (...) {
                return false;
            }
            if (out.ngram < 1 || out.ngram > 3) return false;
        } else if (arg == "--normalize") {
            if (i + 1 >= argc) return false;
            const std::string_view v = argv[++i];
            if (v == "stem") out.normalize_stem = true;
            else if (v == "none") out.normalize_stem = false;
            else return false;
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

// Resolve a --stopwords argument: "ru"/"en" become bundled paths next to the
// executable (data/stop_words_<lang>.txt); anything else is treated literally.
std::string resolve_stopwords_path(const std::string &arg, const char *argv0) {
    if (arg != "ru" && arg != "en") return arg;
    try {
        const auto exe_dir = std::filesystem::weakly_canonical(
            std::filesystem::path(argv0)).parent_path();
        const auto candidate = exe_dir / "data" / ("stop_words_" + arg + ".txt");
        if (std::filesystem::exists(candidate)) return candidate.string();
        // Fall back to a CWD-relative lookup so running ./analyzer from the
        // project root also works during development.
        const auto cwd_candidate =
            std::filesystem::current_path() / "data" / ("stop_words_" + arg + ".txt");
        return cwd_candidate.string();
    } catch (...) {
        return "data/stop_words_" + arg + ".txt";
    }
}

}  // namespace

int main(int argc, char *argv[]) {
    Args args;
    if (!parse_args(argc, argv, args)) {
        print_usage(std::cerr);
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
    const bool filter_stopwords = !args.stopwords_arg.empty();
    if (filter_stopwords) {
        const std::string path = resolve_stopwords_path(args.stopwords_arg, argv[0]);
        stop_words = analyzer::load_stop_words(path);
    }

    const std::vector<std::string> tokens = analyzer::tokenize_utf8(text);

    // Language detection runs on the raw token stream (before stop-word
    // filtering / stemming) so the verdict reflects actual content.
    const std::string language = analyzer::detect_language(tokens);
    const analyzer::ReadabilityResult readability =
        analyzer::compute_readability(text, tokens, language);

    // Pipeline: count total → stop-word filter → optional stem → record into
    // freq map AND into a kept-token sequence used for n-grams. When stemming
    // is on we also remember which original tokens fed each stem (and each
    // stem-phrase) so the displayed label can be the most frequent *original*
    // form instead of the bare stem (e.g. "сказал" instead of "сказа").
    std::unordered_map<std::string, int> freq;
    std::unordered_map<std::string, std::unordered_map<std::string, int>> stem_to_origs;
    std::vector<std::string> kept;
    std::vector<std::string> kept_orig;
    kept.reserve(tokens.size());
    if (args.normalize_stem) kept_orig.reserve(tokens.size());
    long long total = 0;
    for (const auto &token : tokens) {
        ++total;
        if (filter_stopwords && stop_words.count(token)) continue;
        std::string key = args.normalize_stem ? analyzer::stem_token(token) : token;
        ++freq[key];
        if (args.normalize_stem) {
            ++stem_to_origs[key][token];
            kept_orig.push_back(token);
        }
        kept.push_back(std::move(key));
    }

    auto pick_display = [](const std::unordered_map<std::string, int> &m) {
        const std::string *best = nullptr;
        int best_c = -1;
        for (const auto &[w, c] : m) {
            if (c > best_c) { best_c = c; best = &w; }
        }
        return best ? *best : std::string{};
    };

    std::vector<std::pair<std::string, int>> sorted;
    if (args.normalize_stem) {
        std::unordered_map<std::string, int> display_freq;
        display_freq.reserve(freq.size());
        for (const auto &[stem, count] : freq) {
            std::string disp = pick_display(stem_to_origs[stem]);
            if (disp.empty()) disp = stem;
            display_freq[disp] += count;
        }
        sorted.assign(display_freq.begin(), display_freq.end());
    } else {
        sorted.assign(freq.begin(), freq.end());
    }
    std::sort(sorted.begin(), sorted.end(),
              [](const auto &a, const auto &b) { return b.second < a.second; });

    std::vector<std::pair<std::string, int>> ngram_sorted;
    if (args.ngram >= 2) {
        if (args.normalize_stem) {
            // Build stem-phrase frequencies, tracking which original phrase
            // (joined originals) most commonly produced each stem-phrase.
            std::unordered_map<std::string, int> ng_freq;
            std::unordered_map<std::string, std::unordered_map<std::string, int>> phrase_to_origs;
            const int n = args.ngram;
            if (kept.size() >= static_cast<std::size_t>(n)) {
                const std::size_t end_i = kept.size() - static_cast<std::size_t>(n) + 1;
                for (std::size_t i = 0; i < end_i; ++i) {
                    std::string sp = kept[i];
                    std::string op = kept_orig[i];
                    for (int k = 1; k < n; ++k) {
                        sp.push_back(' '); sp.append(kept[i + k]);
                        op.push_back(' '); op.append(kept_orig[i + k]);
                    }
                    ++ng_freq[sp];
                    ++phrase_to_origs[sp][op];
                }
            }
            std::unordered_map<std::string, int> display_ng;
            display_ng.reserve(ng_freq.size());
            for (const auto &[sp, count] : ng_freq) {
                std::string disp = pick_display(phrase_to_origs[sp]);
                if (disp.empty()) disp = sp;
                display_ng[disp] += count;
            }
            ngram_sorted.assign(display_ng.begin(), display_ng.end());
        } else {
            auto ng = analyzer::build_ngrams(kept, args.ngram);
            ngram_sorted.assign(ng.begin(), ng.end());
        }
        std::sort(ngram_sorted.begin(), ngram_sorted.end(),
                  [](const auto &a, const auto &b) { return b.second < a.second; });
    }

    analyzer::JsonWriter w(std::cout);
    w.begin_object();
    w.kv_int("total_words", total);
    w.kv_int("unique_words", static_cast<long long>(sorted.size()));

    w.key("frequencies");
    w.begin_object();
    for (const auto &[word, count] : sorted) {
        w.kv_int(word, count);
    }
    w.end_object();

    if (args.ngram >= 2) {
        w.key("ngrams");
        w.begin_object();
        w.key(std::to_string(args.ngram));
        w.begin_object();
        for (const auto &[phrase, count] : ngram_sorted) {
            w.kv_int(phrase, count);
        }
        w.end_object();
        w.end_object();
    }

    w.kv_string("language", language);

    w.key("readability");
    w.begin_object();
    w.kv_int("words", readability.words);
    w.kv_int("sentences", readability.sentences);
    w.kv_int("syllables", readability.syllables);
    w.kv_double("avg_word_length", readability.avg_word_length);
    w.kv_double("avg_sentence_length", readability.avg_sentence_length);
    w.kv_double("flesch", readability.flesch);
    w.end_object();

    w.kv_string("normalize", args.normalize_stem ? "stem" : "none");
    w.end_object();
    std::cout << '\n';
    return 0;
}
