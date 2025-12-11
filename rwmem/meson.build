
inih_dep = dependency('inih', required : false)
cli11_dep = dependency('CLI11', required : true)

rwmem_sources = files([
    'cmdline.cpp',
    'helpers.cpp',
    'opts.cpp',
    'rwmem.cpp',
])

rwmem_deps = [ librwmem_dep, libfmt_dep, cli11_dep ]

rwmem_args = [ ]

if inih_dep.found()
    rwmem_sources += files([
        'inifile.cpp',
        'inireader.cpp',
    ])
    rwmem_deps += [ inih_dep ]
    rwmem_args += [ '-DHAS_INIH' ]
endif

rwmem_exe = executable('rwmem', rwmem_sources,
                       dependencies : rwmem_deps,
                       cpp_args : rwmem_args,
                       install : true)
