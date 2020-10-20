#!/bin/sh

dirs="librwmem rwmem py"
find $dirs \( -name "*.cpp" -o -name "*.h" \) -exec clang-format -i {} \;
