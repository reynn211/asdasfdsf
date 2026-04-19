#include "analyzer/tokenizer.hpp"

#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace {

void expect_tokens(
    const std::string &name,
    const std::vector<std::string> &got,
    const std::vector<std::string> &expected
) {
    if (got == expected) {
        return;
    }

    auto hex_dump = [](const std::string &s) {
        for (unsigned char c : s) {
            std::cout << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c) << " ";
        }
        std::cout << std::dec << std::setfill(' ') << std::endl;
    };

    std::cerr << name << " failed" << std::endl;
    std::cerr << "  got (" << got.size() << "): ";
    for (const auto &token : got) {
        std::cerr << "[" << token << "] ";
    }
    std::cerr << std::endl;

    std::cerr << "  exp (" << expected.size() << "): ";
    for (const auto &token : expected) {
        std::cerr << "[" << token << "] ";
    }
    std::cerr << std::endl;

    std::cerr << "  got hex: ";
    for (const auto &token : got) {
        std::cerr << "(";
        hex_dump(token);
    }

    std::cerr << "  exp hex: ";
    for (const auto &token : expected) {
        std::cerr << "(";
        hex_dump(token);
    }

    std::exit(1);
}

}  // namespace

static const std::string k_mir = "\xD0\xBC\xD0\xB8\xD1\x80";      // мир
static const std::string k_eto = "\xD0\xB5\xD1\x82\xD0\xBE";      // это
static const std::string k_i = "\xD0\xB8";                        // и
static const std::string k_coffee = "\xD0\xBA\xD0\xBE\xD1\x84\xD0\xB5"; // кофе
static const std::string k_break = "\xD0\xB1\xD1\x80\xD0\xB5\xD0\xB9\xD0\xBA"; // брейк
static const std::string k_vot = "\xD0\xB2\xD0\xBE\xD1\x82"; // вот
static const std::string k_test = "\xD1\x82\xD0\xB5\xD1\x81\xD1\x82"; // тест

int main() {
    expect_tokens(
        "mixed_text",
        analyzer::tokenize_utf8("Hello, " + k_mir + "! " + k_eto + "-test " + k_i + " 123; AI-powered."),
        {"hello", k_mir, k_eto, "test", k_i, "123", "ai", "powered"}
    );

    expect_tokens(
        "hyphen_off",
        analyzer::tokenize_utf8(k_coffee + "-" + k_break + " " + k_i),
        {k_coffee, k_break, k_i}
    );

    expect_tokens(
        "hyphen_on",
        analyzer::tokenize_utf8(k_coffee + "-" + k_break + " " + k_i, true),
        {k_coffee + "-" + k_break, k_i}
    );

    expect_tokens(
        "unicode_dash_delim",
        analyzer::tokenize_utf8(k_vot + "\xE2\x80\x94" + k_test),
        {k_vot, k_test}
    );

    expect_tokens(
        "multiple_punct",
        analyzer::tokenize_utf8(k_mir + "... " + "hello/world"),
        {k_mir, "hello", "world"}
    );

    return 0;
}

