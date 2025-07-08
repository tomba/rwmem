librwmem_sources = files([
    'i2ctarget.cpp',
    'mmaptarget.cpp',
    'regfiledata.cpp',
    'regs.cpp',
])

public_includes = include_directories('.')

librwmem_deps = [ libfmt_dep ]

librwmem = static_library('rwmem',
                          librwmem_sources,
                          dependencies : librwmem_deps)

librwmem_dep = declare_dependency(include_directories : public_includes,
                                  link_with : librwmem)
