# Unit tests for rwmem

gtest_dep = dependency('gtest', main : true, required : false)
if not gtest_dep.found()
  gtest_dep = disabler()
endif

test_data_generator_lib = static_library('test_data_generator',
    'test_data_generator.cpp',
    include_directories : include_directories('..'),
    dependencies : [libfmt_dep],
)

generate_test_regdb = executable('generate_test_regdb',
    'generate_test_regdb.cpp',
    include_directories : include_directories('..'),
    link_with : [test_data_generator_lib],
    dependencies : [libfmt_dep],
    build_by_default : false,
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

# Python tests
python3 = find_program('python3')

test('rwmem_cmd_tests', python3,
    args : ['-m', 'unittest', 'discover', '-v', meson.current_source_dir()],
    env : {'RWMEM_CMD': rwmem_exe.full_path()},
    depends : [rwmem_exe]
)
