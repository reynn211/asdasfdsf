cmake_minimum_required(VERSION 3.12)

project(vk_nlp_analyzer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(analyzer_core
    src/tokenizer.cpp
    src/stop_words.cpp
)

target_include_directories(analyzer_core
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

add_executable(analyzer
    src/analyzer_main.cpp
)

target_link_libraries(analyzer
    PRIVATE
        analyzer_core
)

set_target_properties(analyzer PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)

enable_testing()

add_executable(tokenizer_tests
    tests/tokenizer_tests.cpp
)

target_link_libraries(tokenizer_tests
    PRIVATE
        analyzer_core
)

add_test(NAME tokenizer_tests COMMAND tokenizer_tests)
