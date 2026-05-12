cmake_minimum_required(VERSION 3.19)
project(
        sts_lightspeed
        VERSION 0.1
        DESCRIPTION "High Performance, rng accurate implementation of Slay the Spire with tools for tree search and ml."
        LANGUAGES CXX)

file (GLOB_RECURSE sts_lightspeed_SOURCES CONFIGURE_DEPENDS "src/*.cpp")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_FLAGS  "-Wno-shift-count-overflow -O3")

add_subdirectory(json)
add_subdirectory(pybind11)

pybind11_add_module(slaythespire bindings/slaythespire.cpp bindings/bindings-util.cpp ${sts_lightspeed_SOURCES})
target_include_directories(slaythespire PUBLIC include)
target_include_directories(slaythespire PUBLIC json/single_include)
target_include_directories(slaythespire PUBLIC bindings)


add_executable(main apps/main.cpp ${sts_lightspeed_SOURCES})
target_link_libraries(main PRIVATE nlohmann_json::nlohmann_json)
target_include_directories(main PUBLIC include)
target_include_directories(main PUBLIC json/single_include)

add_executable(test apps/test.cpp ${sts_lightspeed_SOURCES})
target_include_directories(test PUBLIC include)
target_link_libraries(test PUBLIC nlohmann_json::nlohmann_json)
target_include_directories(test PUBLIC json/single_include)

add_executable(small-test apps/small-test.cpp bindings/bindings-util.cpp ${sts_lightspeed_SOURCES})
target_link_libraries(small-test PRIVATE nlohmann_json::nlohmann_json)
target_include_directories(small-test PUBLIC include)
target_include_directories(small-test PUBLIC json/single_include)
target_include_directories(small-test PUBLIC bindings)

# Wheel install: scikit-build-core picks up these install() rules and
# packages the .so into the wheel (alongside the python/sts_lightspeed
# package). Only the Python extension is installed; the C++ test apps
# are dev-only.
if(SKBUILD)
    install(TARGETS slaythespire LIBRARY DESTINATION .)
endif()
