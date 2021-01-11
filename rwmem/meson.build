inih_dep = dependency('inih', fallback : ['inih', 'inih_dep'])

rwmem_sources = files([
    'cmdline.cpp',
    'inifile.cpp',
    'inireader.cpp',
    'opts.cpp',
    'rwmem.cpp',
])

executable('rwmem', rwmem_sources,
           dependencies : [ librwmem_dep, inih_dep, libfmt_dep ],
           install : true,
           cpp_args : '-DINI_ALLOW_MULTILINE=0',
           c_args : '-DINI_ALLOW_MULTILINE=0')
