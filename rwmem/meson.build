
inih_dep = dependency('inih', required : false)

rwmem_sources = files([
    'cmdline.cpp',
    'opts.cpp',
    'rwmem.cpp',
])

rwmem_deps = [ librwmem_dep, libfmt_dep ]

rwmem_args = [ ]

if inih_dep.found()
    rwmem_sources += files([
        'inifile.cpp',
        'inireader.cpp',
    ])
    rwmem_deps += [ inih_dep ]
    rwmem_args += [ '-DHAS_INIH' ]
endif

executable('rwmem', rwmem_sources,
           dependencies : rwmem_deps,
           cpp_args : rwmem_args,
           install : true)
