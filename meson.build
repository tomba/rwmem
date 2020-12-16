project('rwmem', 'cpp', 'c',
    default_options : [
        'cpp_std=c++17',
    ],
)

cpp = meson.get_compiler('cpp')
cpp_arguments = []

if (cpp.get_id() == 'gcc' and
    host_machine.cpu_family() == 'arm' and
    cpp.has_argument('-Wno-psabi'))
    cpp_arguments += [
        '-Wno-psabi',
    ]
endif

add_project_arguments(cpp_arguments, language : 'cpp')

link_arguments = []

if get_option('static-libc')
    link_arguments += ['-static-libgcc', '-static-libstdc++']
endif

add_global_link_arguments(link_arguments, language : 'cpp')

subdir('librwmem')
subdir('rwmem')
subdir('py')
