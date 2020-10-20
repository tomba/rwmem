rwmem_sources = files([
    'cmdline.cpp',
    'inifile.cpp',
    'inireader.cpp',
    'opts.cpp',
    'rwmem.cpp',
    '../ext/inih/ini.c',
])

executable('rwmem', rwmem_sources,
           include_directories : [ '../ext/inih' ],
           dependencies : [ librwmem_dep ], install : true,
           cpp_args : '-DINI_ALLOW_MULTILINE=0',
           c_args : '-DINI_ALLOW_MULTILINE=0')
