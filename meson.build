project('rwmem', 'cpp', 'c',
    version : '2.0.0',
    default_options : [
        'cpp_std=c++20',
        'warning_level=3',
    ],
)

cpp = meson.get_compiler('cpp')
cpp_arguments = []

cpp_arguments += [
    '-Wno-unused-parameter',
]

if (cpp.get_id() == 'gcc' and
    host_machine.cpu_family() == 'arm' and
    cpp.has_argument('-Wno-psabi'))
    cpp_arguments += [
        '-Wno-psabi',
    ]
endif

add_project_arguments(cpp_arguments, language : 'cpp')

libfmt_dep = dependency('fmt', fallback : ['fmt', 'fmt_dep'])

subdir('librwmem')
subdir('rwmem')
