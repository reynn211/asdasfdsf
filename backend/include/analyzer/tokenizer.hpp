#pragma once

#include <string>
#include <string_view>
#include <vector>

namespace analyzer {

std::vector<std::string> tokenize_utf8(std::string_view text,
                                       bool keep_internal_hyphen = false);

}  // namespace analyzer
