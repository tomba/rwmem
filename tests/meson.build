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

test('regfiledata', test_regfiledata)