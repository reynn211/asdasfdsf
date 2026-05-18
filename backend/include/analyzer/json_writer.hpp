#pragma once

#include <cstdio>
#include <limits>
#include <ostream>
#include <string>
#include <string_view>

namespace analyzer {

// Minimal JSON writer for the analyzer output. Tracks whether the next item
// inside the currently-open object needs a leading comma. Caller is responsible
// for matching begin_object()/end_object() and emitting keys before nested
// objects via key().
class JsonWriter {
public:
    explicit JsonWriter(std::ostream &os) : os_(os) {}

    void begin_object() {
        if (need_comma_) os_ << ',';
        os_ << '{';
        need_comma_ = false;
    }

    void end_object() {
        os_ << '}';
        need_comma_ = true;
    }

    // Write "k":v where v is an integer.
    void kv_int(std::string_view k, long long v) {
        if (need_comma_) os_ << ',';
        write_string(k);
        os_ << ':' << v;
        need_comma_ = true;
    }

    // Write "k":v where v is a floating-point number. NaN/Inf are written
    // as null to keep output strictly JSON-valid.
    void kv_double(std::string_view k, double v) {
        if (need_comma_) os_ << ',';
        write_string(k);
        os_ << ':';
        if (!(v == v) || v == std::numeric_limits<double>::infinity() ||
            v == -std::numeric_limits<double>::infinity()) {
            os_ << "null";
        } else {
            char buf[32];
            std::snprintf(buf, sizeof(buf), "%.3f", v);
            os_ << buf;
        }
        need_comma_ = true;
    }

    // Write "k":"v".
    void kv_string(std::string_view k, std::string_view v) {
        if (need_comma_) os_ << ',';
        write_string(k);
        os_ << ':';
        write_string(v);
        need_comma_ = true;
    }

    // Write "k": and leave the next call (typically begin_object) to emit the value.
    void key(std::string_view k) {
        if (need_comma_) os_ << ',';
        write_string(k);
        os_ << ':';
        need_comma_ = false;
    }

private:
    void write_string(std::string_view s) {
        os_ << '"';
        for (char c : s) {
            unsigned char u = static_cast<unsigned char>(c);
            if (c == '"') os_ << "\\\"";
            else if (c == '\\') os_ << "\\\\";
            else if (c == '\n') os_ << "\\n";
            else if (c == '\r') os_ << "\\r";
            else if (c == '\t') os_ << "\\t";
            else if (u < 0x20) {
                char buf[8];
                std::snprintf(buf, sizeof(buf), "\\u%04x", u);
                os_ << buf;
            } else {
                os_ << c;
            }
        }
        os_ << '"';
    }

    std::ostream &os_;
    bool need_comma_ = false;
};

}  // namespace analyzer
