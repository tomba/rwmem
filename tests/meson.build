# Unit tests for rwmem

gtest_dep = dependency('gtest', main : true, required : false)
if not gtest_dep.found()
  gtest_dep = disabler()
endif

test_regfiledata = executable('test_regfiledata',
    'test_regfiledata.cpp',
    include_directories : include_directories('..'),
    link_with : [librwmem],
    dependencies : [gtest_dep],
    cpp_args : ['-DTEST_DATA_DIR="' + meson.current_source_dir() + '"'],
)

test_mmaptarget = executable('test_mmaptarget',
    'test_mmaptarget.cpp',
    include_directories : include_directories('..'),
    link_with : [librwmem],
    dependencies : [gtest_dep],
    cpp_args : ['-DTEST_DATA_DIR="' + meson.current_source_dir() + '"'],
)

test_opts = executable('test_opts',
    'test_opts.cpp',
    '../rwmem/opts.cpp',
    include_directories : include_directories('..'),
    dependencies : [gtest_dep],
)

test('regfiledata', test_regfiledata)
test('mmaptarget', test_mmaptarget)
test('opts', test_opts)

# Python tests
python3 = find_program('python3')

test('rwmem_cmd_tests', python3,
    args : ['-m', 'unittest', 'discover', '-v', meson.current_source_dir()],
    env : {'RWMEM_CMD': rwmem_exe.full_path()},
    depends : [rwmem_exe]
)
