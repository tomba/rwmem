librwmem_sources = files([
    'helpers.cpp',
    'i2ctarget.cpp',
    'mmaptarget.cpp',
    'regfiledata.cpp',
    'regs.cpp',
])

public_includes = include_directories('.')

librwmem = library('kms++',
                   librwmem_sources,
                   install : true)

librwmem_dep = declare_dependency(include_directories : public_includes,
                                  link_with : librwmem)
