#include "analyzer/ngrams.hpp"
#include "analyzer/stemmer.hpp"

#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

namespace {

int failures = 0;

void expect_eq(const std::string &name, const std::string &got, const std::string &want) {
    if (got == want) return;
    ++failures;
    std::cerr << name << " failed: got [" << got << "], want [" << want << "]\n";
}

void expect_count(const std::string &name,
                  const std::unordered_map<std::string, int> &m,
                  const std::string &key,
                  int want) {
    auto it = m.find(key);
    const int got = (it == m.end()) ? 0 : it->second;
    if (got == want) return;
    ++failures;
    std::cerr << name << " failed: key [" << key << "] got " << got << ", want " << want << "\n";
}

}  // namespace

int main() {
    // ---- English Porter spot checks --------------------------------------
    // Classic Porter examples from the 1980 paper / Snowball test set.
    expect_eq("en/connections", analyzer::stem_en("connections"), "connect");
    expect_eq("en/connected",   analyzer::stem_en("connected"),   "connect");
    expect_eq("en/connecting",  analyzer::stem_en("connecting"),  "connect");
    expect_eq("en/agreed",      analyzer::stem_en("agreed"),      "agre");
    expect_eq("en/relational",  analyzer::stem_en("relational"),  "relat");
    expect_eq("en/conditional", analyzer::stem_en("conditional"), "condit");
    expect_eq("en/happy",       analyzer::stem_en("happy"),       "happi");
    expect_eq("en/sky",         analyzer::stem_en("sky"),         "sky");
    expect_eq("en/caresses",    analyzer::stem_en("caresses"),    "caress");
    expect_eq("en/ponies",      analyzer::stem_en("ponies"),      "poni");

    // Short / edge cases.
    expect_eq("en/ai",          analyzer::stem_en("ai"),          "ai");
    expect_eq("en/a",           analyzer::stem_en("a"),           "a");

    // ---- Russian Snowball spot checks ------------------------------------
    // All-form conflation: declensions of "стол" collapse to a common stem.
    const std::string stol      = analyzer::stem_ru(u8"стол");
    const std::string stolami   = analyzer::stem_ru(u8"столами");
    const std::string stolu     = analyzer::stem_ru(u8"столу");
    const std::string stolakh   = analyzer::stem_ru(u8"столах");
    expect_eq("ru/stol-vs-stolami", stol, stolami);
    expect_eq("ru/stol-vs-stolu",   stol, stolu);
    expect_eq("ru/stol-vs-stolakh", stol, stolakh);

    // Adjective conflation.
    const std::string krasivyj = analyzer::stem_ru(u8"красивый");
    const std::string krasivaya = analyzer::stem_ru(u8"красивая");
    const std::string krasivoe  = analyzer::stem_ru(u8"красивое");
    expect_eq("ru/krasiv-m-vs-f",  krasivyj, krasivaya);
    expect_eq("ru/krasiv-m-vs-n",  krasivyj, krasivoe);

    // Verb forms.
    const std::string chital   = analyzer::stem_ru(u8"читал");
    const std::string chitala  = analyzer::stem_ru(u8"читала");
    const std::string chitali  = analyzer::stem_ru(u8"читали");
    expect_eq("ru/chital-vs-chitala", chital, chitala);
    expect_eq("ru/chital-vs-chitali", chital, chitali);

    // Idempotence: stemming a stem should be a no-op.
    expect_eq("ru/idempotent", analyzer::stem_ru(stol), stol);
    expect_eq("en/idempotent", analyzer::stem_en("connect"), "connect");

    // ---- Dispatcher: per-token script routing ----------------------------
    expect_eq("dispatch/cyr",  analyzer::stem_token(u8"столами"), stol);
    expect_eq("dispatch/lat",  analyzer::stem_token("connections"), "connect");
    expect_eq("dispatch/num",  analyzer::stem_token("12345"), "12345");
    expect_eq("dispatch/mixed",analyzer::stem_token(u8"abc123"), "abc123");

    // ---- N-grams ---------------------------------------------------------
    const std::vector<std::string> toks = {"the", "quick", "brown", "fox", "the", "quick"};
    auto bi = analyzer::build_ngrams(toks, 2);
    expect_count("ngram/bi/the-quick",   bi, "the quick", 2);
    expect_count("ngram/bi/quick-brown", bi, "quick brown", 1);
    expect_count("ngram/bi/brown-fox",   bi, "brown fox", 1);
    expect_count("ngram/bi/fox-the",     bi, "fox the", 1);

    auto tri = analyzer::build_ngrams(toks, 3);
    expect_count("ngram/tri/the-quick-brown", tri, "the quick brown", 1);
    expect_count("ngram/tri/quick-brown-fox", tri, "quick brown fox", 1);

    auto empty = analyzer::build_ngrams({"a", "b"}, 3);
    if (!empty.empty()) {
        ++failures;
        std::cerr << "ngram/short: expected empty map, got " << empty.size() << " entries\n";
    }

    if (failures > 0) {
        std::cerr << failures << " test(s) failed\n";
        return 1;
    }
    std::cout << "stemmer_tests: all passed\n";
    return 0;
}
