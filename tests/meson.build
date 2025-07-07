# Unit tests for rwmem

gtest_dep = dependency('gtest', main : true)

test_data_generator_lib = static_library('test_data_generator',
    'test_data_generator.cpp',
    include_directories : include_directories('..'),
    dependencies : [libfmt_dep],
)

test_regfiledata = executable('test_regfiledata',
    'test_regfiledata.cpp',
    include_directories : include_directories('..'),
    link_with : [librwmem, test_data_generator_lib],
    dependencies : [libfmt_dep, gtest_dep],
)

test_mmaptarget = executable('test_mmaptarget',
    'test_mmaptarget.cpp',
    include_directories : include_directories('..'),
    link_with : [librwmem],
    dependencies : [libfmt_dep, gtest_dep],
    cpp_args : ['-DTEST_DATA_DIR="' + meson.current_source_dir() + '"'],
)

test('regfiledata', test_regfiledata)
test('mmaptarget', test_mmaptarget)