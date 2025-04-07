# SPDX-License-Identifier: Apache-2.0
# Copyright 2019-2022 The meson development team

from __future__ import annotations

import typing as T

from ... import mesonlib
from ..compilers import CompileCheckMode
from .gnu import GnuLikeCompiler, gnu_color_args, gnu_optimization_args
from ...options import OptionKey

if T.TYPE_CHECKING:
    from ...environment import Environment

class QnxCompiler(GnuLikeCompiler):
    """
    QNX compiler
    https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/q/qcc.html
    """
    id = 'qcc'

    def __init__(self, defines: T.Optional[T.Dict[str, str]]):
        super().__init__()
        self.defines = defines or {}
        self.base_options.update({OptionKey('b_colorout'), OptionKey('b_lto_threads')})
        self._has_color_support = mesonlib.version_compare(self.version, '>=4.9.0')
        self._has_wpedantic_support = mesonlib.version_compare(self.version, '>=4.8.0')
        self._has_lto_auto_support = mesonlib.version_compare(self.version, '>=10.0')

    def get_colorout_args(self, colortype: str) -> T.List[str]:
        if self._has_color_support:
            return gnu_color_args[colortype][:]
        return []

    def get_warn_args(self, level: str) -> T.List[str]:
        # Mypy doesn't understand cooperative inheritance
        args = super().get_warn_args(level)
        if not self._has_wpedantic_support and '-Wpedantic' in args:
            # -Wpedantic was added in 4.8.0
            # https://gcc.gnu.org/gcc-4.8/changes.html
            args[args.index('-Wpedantic')] = '-pedantic'
        return args

    def supported_warn_args(self, warn_args_by_version: T.Dict[str, T.List[str]]) -> T.List[str]:
        result: T.List[str] = []
        for version, warn_args in warn_args_by_version.items():
            if mesonlib.version_compare(self.version, '>=' + version):
                result += warn_args
        return result

    def has_builtin_define(self, define: str) -> bool:
        return define in self.defines

    def get_builtin_define(self, define: str) -> T.Optional[str]:
        if define in self.defines:
            return self.defines[define]
        return None

    def get_optimization_args(self, optimization_level: str) -> T.List[str]:
        return gnu_optimization_args[optimization_level]

    def get_pch_suffix(self) -> str:
        return 'gch'

    def openmp_flags(self, env: Environment) -> T.List[str]:
        return ['-fopenmp']

    def has_arguments(self, args: T.List[str], env: 'Environment', code: str,
                      mode: CompileCheckMode) -> T.Tuple[bool, bool]:
        # For some compiler command line arguments, the GNU compilers will
        # emit a warning on stderr indicating that an option is valid for a
        # another language, but still complete with exit_success
        with self._build_wrapper(code, env, args, None, mode) as p:
            result = p.returncode == 0
            if self.language in {'cpp', 'objcpp'} and 'is valid for C/ObjC' in p.stderr:
                result = False
            if self.language in {'c', 'objc'} and 'is valid for C++/ObjC++' in p.stderr:
                result = False
        return result, p.cached

    def get_has_func_attribute_extra_args(self, name: str) -> T.List[str]:
        # GCC only warns about unknown or ignored attributes, so force an
        # error.
        return ['-Werror=attributes']

    def get_prelink_args(self, prelink_name: str, obj_list: T.List[str]) -> T.Tuple[T.List[str], T.List[str]]:
        return [prelink_name], ['-r', '-o', prelink_name] + obj_list

    def get_lto_compile_args(self, *, threads: int = 0, mode: str = 'default') -> T.List[str]:
        if threads == 0:
            if self._has_lto_auto_support:
                return ['-flto=auto']
            # This matches clang's behavior of using the number of cpus, but
            # obeying meson's MESON_NUM_PROCESSES convention.
            return [f'-flto={mesonlib.determine_worker_count()}']
        elif threads > 0:
            return [f'-flto={threads}']
        return super().get_lto_compile_args(threads=threads)

    @classmethod
    def use_linker_args(cls, linker: str, version: str) -> T.List[str]:
        if linker == 'mold' and mesonlib.version_compare(version, '>=12.0.1'):
            return ['-fuse-ld=mold']
        return super().use_linker_args(linker, version)

    def get_profile_use_args(self) -> T.List[str]:
        return super().get_profile_use_args() + ['-fprofile-correction']

    def get_dependency_gen_args(self, outtarget: str, outfile: str) -> T.List[str]:
        return ['-Wc,-MT,'+outtarget, '-Wc,-MMD', '-Wc,-MP', '-Wc,-MF,'+outfile]
