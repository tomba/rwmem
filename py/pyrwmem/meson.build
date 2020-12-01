py3_dep = dependency('python3', required : get_option('pyrwmem'))

if py3_dep.found() == false
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

pyrwmem = shared_module('pyrwmem',
                      pyrwmem_sources,
                      install : true,
                      install_dir : destdir,
                      name_prefix : '',
                      dependencies : pyrwmem_deps,
                      cpp_args : pyrwmem_args)

# Copy __init__.py to build dir so that we can run without installing
configure_file(input: '__init__.py', output: '__init__.py', copy: true,
               install : true, install_dir : destdir)
