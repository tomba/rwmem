file(GLOB SRCS "*.cpp" "*.h")
add_library(rwmem-lib ${SRCS})

SET_TARGET_PROPERTIES(rwmem-lib PROPERTIES OUTPUT_NAME rwmem)
