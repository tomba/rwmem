py3_dep = dependency('python3', required : get_option('pyrwmem'))

if py3_dep.found() == false
    subdir_done()
endif

pybind11_dep = dependency('pybind11', fallback : ['pybind11', 'pybind11_dep'],
                          required : get_option('pyrwmem'))

if pybind11_dep.found() == false
    subdir_done()
endif

pyrwmem_sources = files([
    'pyrwmem.cpp',
])

pyrwmem_deps = [
    librwmem_dep,
    py3_dep,
    pybind11_dep,
]

pyrwmem_args = [ '-fvisibility=hidden' ]

destdir = get_option('libdir') / 'python' + py3_dep.version() / 'site-packages/pyrwmem'

pyrwmem = shared_module('rwmem',
                      pyrwmem_sources,
                      install : true,
                      install_dir : destdir,
                      name_prefix : '',
                      dependencies : pyrwmem_deps,
                      cpp_args : pyrwmem_args)

# Create symlinks from the build dir to the source dir so that we can use the
# Python module directly from the build dir.

pyfiles = [
    '__init__.py',
    'mappedregister.py',
]

foreach file : pyfiles
    run_command('ln', '-fsrT', files(file),
                meson.current_build_dir() / file,
                check : true)
endforeach
