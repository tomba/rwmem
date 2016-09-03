file(GLOB SRCS "*.cpp" "*.h")

add_library(rwmem-lib ${SRCS})
set_target_properties(rwmem-lib PROPERTIES OUTPUT_NAME rwmem)
target_include_directories(rwmem-lib PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
