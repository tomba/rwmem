include_directories(${PROJECT_SOURCE_DIR}/ext/inih)

file(GLOB SOURCES "*.cpp" "*.h")

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -DINI_ALLOW_MULTILINE=0")
set(SOURCES ${SOURCES} ${PROJECT_SOURCE_DIR}/ext/inih/ini.c ${PROJECT_SOURCE_DIR}/ext/inih/ini.h)

add_executable (rwmem-bin ${SOURCES})
target_link_libraries(rwmem-bin rwmem-lib)

SET_TARGET_PROPERTIES(rwmem-bin PROPERTIES OUTPUT_NAME rwmem)
