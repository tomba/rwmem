include_directories(${PROJECT_SOURCE_DIR}/ext/inih)

file(GLOB SOURCES "*.cpp" "*.h")

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -DINI_ALLOW_MULTILINE=0")
set(SOURCES ${SOURCES} ${PROJECT_SOURCE_DIR}/ext/inih/ini.c ${PROJECT_SOURCE_DIR}/ext/inih/ini.h)

add_executable (rwmem-bin ${SOURCES})
set_target_properties(rwmem-bin PROPERTIES OUTPUT_NAME rwmem)
target_link_libraries(rwmem-bin rwmem-lib)

add_test(NAME rwmem-list
    COMMAND "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/rwmem" --regs py/tests/test.regs --list
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/..)

add_test(NAME rwmem-reg1
    COMMAND "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/rwmem" --mmap py/tests/test.bin --regs py/tests/test.regs BLOCK1.REG1
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/..)

INSTALL(TARGETS rwmem-bin
  RUNTIME DESTINATION bin
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib
)
