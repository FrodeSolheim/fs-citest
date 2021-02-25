#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess

strip = False
rpath = False
no_copy = False
# steam_runtime = os.getenv("STEAM_RUNTIME", "")
# steam_runtime = os.getenv("STEAMOS", "")
steam_runtime = False


excluded_libraries = {}
included_libraries = {}


def fix_linux_binary(path):
    changes = 0
    if os.path.exists(path + ".standalone"):
        return changes
    if not os.path.exists(path):
        raise Exception("could not find " + repr(path))

    # find library locations
    args = ["ldd", path]
    print(args)
    # p = subprocess.Popen(args, stdout=subprocess.PIPE)
    # if p.wait() != 0:
    #     return 0
    p = subprocess.run(args, capture_output=True)
    # noinspection PyUnresolvedReferences
    if p.returncode != 0:
        if p.stderr == b"\tnot a dynamic executable\n":
            pass
        else:
            print(repr(p.stderr))
        return 0
    data = p.stdout.decode("UTF-8")
    print("fixing", path, "no_copy =", no_copy)
    library_locations = {}
    for line in data.split("\n"):
        line = line.strip()
        if "=>" not in line:
            continue
        library_locations[line.split(" ")[0]] = line.split(" ")[2]

    # find direct dependencies
    args = ["objdump", "-p", path]
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    # noinspection PyUnresolvedReferences
    data = p.stdout.read().decode("UTF-8")
    if p.wait() != 0:
        return 0
    for line in data.split("\n"):
        line = line.strip()
        # print(line)
        if not line.startswith("NEEDED"):
            continue
        print(line)
        library = line.split(" ")[-1]
        print(library)
        if ignore_linux_library(library):
            excluded_libraries.setdefault(library, set()).add(path)
            continue
        library_source = library_locations[library]
        library_source = os.path.normpath(library_source)
        print(library, library_source)
        # if steam_runtime and library_source.startswith(steam_runtime):
        # if steam_runtime and not library_source.startswith("/usr/local"):
        # if steam_runtime and not library_source.startswith("/home"):
        #     print("skipping steam runtime library")
        #     excluded_libraries.setdefault(library_source, set()).add(path)
        #     continue
        if no_copy:
            print("no_copy is set")
            continue
        dst = os.path.join(os.path.dirname(path), library)
        if not os.path.exists(dst):
            print("[FSBUILD] Copy", library_source)
            print("Needed by:", path)
            shutil.copy(library_source, dst)
            os.chmod(dst, 0o644)
            included_libraries.setdefault(library_source, set()).add(path)
            changes += 1
    if strip:
        # strip does not work after patchelf has been run
        command = "strip '{}'".format(path)
        print(command)
        os.system(command)
    if rpath:
        command = "patchelf --set-rpath '{}' '{}'".format(rpath, path)
        print(command)
        assert os.system(command) == 0
    # to make sure strip is not run again
    os.system("touch '{}.standalone'".format(path))
    return changes


# FIXME: Print warning if excluded libraries is not in this list?
manylinux2014_whitelist = set(
    [
        "libgcc_s.so.1",
        "libstdc++.so.6",
        "libm.so.6",
        "libdl.so.2",
        "librt.so.1",
        "libc.so.6",
        "libnsl.so.1",
        "libutil.so.1",
        "libpthread.so.0",
        "libresolv.so.2",
        "libX11.so.6",
        "libXext.so.6",
        "libXrender.so.1",
        "libICE.so.6",
        "libSM.so.6",
        "libGL.so.1",
        "libgobject-2.0.so.0",
        "libgthread-2.0.so.0",
        "libglib-2.0.so.0",
    ]
)


def ignore_linux_library(name):
    if os.getenv("LIBGPG_ERROR_CHECK", "") != "0":
        if name.startswith("libgpg-error.so"):
            raise Exception(
                "Bundling libgpg-error (libgcrypt?) breaks Intel GL driver"
            )

    # Skip the dynamic linker for all known architectures
    if name.startswith("linux-gate.so"):
        return True
    if name.startswith("linux-vdso.so"):
        return True
    if name.startswith("ld-linux.so.2"):
        return True
    if name.startswith("ld-linux-x86-64.so"):
        return True
    if name.startswith("ld-linux-armhf.so.3"):
        return True

    # Bundling the C library is a no-no (causes issues)
    if name.startswith("libc.so"):
        return True

    # These are also system and/or libc libraries that we want to skip
    if name.startswith("libpthread.so"):
        return True
    if name.startswith("libm.so"):
        return True
    if name.startswith("libdl.so"):
        return True
    if name.startswith("libresolv.so"):
        return True
    if name.startswith("librt.so"):
        return True
    if name.startswith("libutil.so"):
        return True

    # Including libstdc++.sp breaks libGL loading with Intel on Ubuntu 16.10
    # libGL error: unable to load driver: i965_dri.so
    if name.startswith("libstdc++.so"):
        return True

    # Might as well skip this one also, to avoid potential problems. This
    # probably requires that we compile with a not-too-recent GCC version.
    if name.startswith("libgcc_s.so"):
        return True

    # Problem with OpenAL on Ubuntu 16.04 if this is included
    # if name.startswith("libpcre.so"):
    #     return True

    # OpenGL libraries should definitively not be distributed
    if name.startswith("libGL.so"):
        return True
    if name.startswith("libGLU.so"):
        return True
    if name.startswith("libEGL.so"):
        return True

    # Alsa library is in LSB, looks like only "old" interfaces likely to exist
    # on all system are used by SDL2.
    if name.startswith("libasound.so"):
        return True

    # X libraries are assumed to exist on the host system
    if name.startswith("libX11.so"):
        return True
    if name.startswith("libXext.so"):
        return True
    if name.startswith("libXcursor.so"):
        return True
    if name.startswith("libXinerama.so"):
        return True
    if name.startswith("libXi.so"):
        return True
    if name.startswith("libXrandr.so"):
        return True
    if name.startswith("libXss.so"):
        return True
    if name.startswith("libXxf86vm.so"):
        return True
    # FIXME: Why was this commented out?
    # if name.startswith("libxkbcommon.so"):
    #     return True
    if name.startswith("libxcb.so"):
        return True

    return False


def linux_iteration(app):
    binaries = []
    binaries_dir = app
    for name in sorted(os.listdir(binaries_dir)):
        binaries.append(os.path.join(binaries_dir, name))
    changes = 0
    for binary in binaries:
        changes += fix_linux_binary(binary)
    return changes


def linux_main():
    global no_copy, strip, rpath
    for arg in list(sys.argv):
        if arg.startswith("--rpath="):
            sys.argv.remove(arg)
            rpath = arg[8:]
        elif arg == "--no-copy":
            sys.argv.remove("--no-copy")
            no_copy = True
        elif arg == "--strip":
            sys.argv.remove("--strip")
            strip = True
    app = sys.argv[1]
    while True:
        changes = linux_iteration(app)
        if changes == 0:
            break
    for name in sorted(os.listdir(app)):
        if name.endswith(".standalone"):
            os.remove(os.path.join(app, name))


def fix_macos_binary(path, frameworks_dir):
    if path.endswith(".txt"):
        return 0
    print("fixing", path)
    changes = 0
    if not os.path.exists(path):
        raise Exception("could not find " + repr(path))
    args = ["otool", "-L", path]
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    # noinspection PyUnresolvedReferences
    data = p.stdout.read().decode("UTF-8")
    p.wait()
    for line in data.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.endswith(":"):
            continue
        if line.startswith("/usr/lib") or line.startswith("/System"):
            # old = line.split(" ")[0]
            continue
        if line.startswith("@executable_path"):
            continue
        old = line.split(" ")[0]
        if "Contents" in old:
            continue
        print(old)
        old_dir, name = os.path.split(old)
        # new = old.replace(old, "@executable_path/../Frameworks/" + name)
        if rpath:
            new = old.replace(old, "@rpath/" + name)
        else:
            new = old.replace(old, "@executable_path/" + name)
        if no_copy:
            pass
        else:
            dst = os.path.join(frameworks_dir, os.path.basename(old))
            if not os.path.exists(dst):
                print("[FSBUILD] Copy", old)
                shutil.copy(old, dst)
                os.chmod(dst, 0o644)
                changes += 1
        if os.path.basename(path) == os.path.basename(old):
            args = ["install_name_tool", "-id", new, path]
        else:
            args = ["install_name_tool", "-change", old, new, path]
        print(args)
        p = subprocess.Popen(args)
        assert p.wait() == 0
    if strip:
        if path.endswith(".dylib") or path.endswith(".so"):
            command = "strip -x '{}'".format(path)
        else:
            command = "strip '{}'".format(path)
        print(command)
        os.system(command)
    return changes


def macos_iteration(app):
    binaries = []
    if os.path.isdir(app):
        # mac_os_dir = os.path.join(app, "Contents", "MacOS")
        frameworks_dir = app
        # frameworks_dir = os.path.join(app, "Contents", "Frameworks")
        # for name in sorted(os.listdir(mac_os_dir)):
        #    binaries.append(os.path.join(mac_os_dir, name))
        # for name in os.listdir(frameworks_dir):
        #    binaries.append(os.path.join(frameworks_dir, name))
        for name in sorted(os.listdir(app)):
            binaries.append(os.path.join(app, name))
    else:
        binaries.append(app)
    changes = 0
    for binary in binaries:
        changes += fix_macos_binary(binary, frameworks_dir)
    return changes


def macos_main():
    global rpath, no_copy
    if "--rpath" in sys.argv:
        sys.argv.remove("--rpath")
        rpath = True
    if "--no-copy" in sys.argv:
        sys.argv.remove("--no-copy")
        no_copy = True
    app = sys.argv[1]
    while True:
        changes = macos_iteration(app)
        if changes == 0:
            break


windows_system_dlls = [
    "advapi32.dll",
    "dsound.dll",
    "dwmapi.dll",
    "gdi32.dll",
    "imm32.dll",
    "kernel32.dll",
    "msvcrt.dll",
    "ntdll.dll",
    "ole32.dll",
    "oleaut32.dll",
    "opengl32.dll",
    "rpcrt4.dll",
    "setupapi.dll",
    "shell32.dll",
    "shlwapi.dll",
    "user32.dll",
    "userenv.dll",
    "usp10.dll",
    "uxtheme.dll",
    "version.dll",
    "winmm.dll",
    "ws2_32.dll",
    "wsock32.dll",
]


def fix_windows_binary(path, app_dir):
    if path.endswith(".txt"):
        return 0
    print("fixing", path)
    changes = 0
    if not os.path.exists(path):
        raise Exception("could not find " + repr(path))
    dumpbin = os.environ["VS140COMNTOOLS"] + "..\\..\\VC\\bin\\dumpbin.exe"
    args = [dumpbin, "/DEPENDENTS", path]
    print(args)
    p = subprocess.Popen(args, shell=True, stdout=subprocess.PIPE)
    # noinspection PyUnresolvedReferences
    data = p.stdout.read().decode("UTF-8")
    p.wait()
    for line in data.split("\n"):
        # print(line)
        line = line.strip()
        if not line:
            continue
        if line.endswith("Summary"):
            break
        if not line.endswith(".dll"):
            continue
        src = line
        if src.lower() in windows_system_dlls:
            continue
        dll_name = src
        print(dll_name)

        if True:
            dst = os.path.join(app_dir, os.path.basename(src))
            if not os.path.exists(dst):
                src = os.path.join("fsdeps", "_prefix", "bin", dll_name)
                print("Checking", src)
                if not os.path.exists(src):
                    src = os.environ["MINGW_PREFIX"] + "/bin/" + dll_name
                    print("Checking", src)
                print(src)
                print("[FSBUILD] Copy", src)
                shutil.copy(src, dst)
                os.chmod(dst, 0o644)
                changes += 1
    if strip:
        command = 'strip "{}"'.format(path)
        print(command)
        os.system(command)
    # Make deterministic exe/dll
    command = 'ducible "{}"'.format(path)
    print(command)
    os.system(command)
    return changes


def windows_iteration(app):
    binaries = []
    if os.path.isdir(app):
        for name in sorted(os.listdir(app)):
            binaries.append(os.path.join(app, name))
    # else:
    #     binaries.append(app)
    changes = 0
    for binary in binaries:
        changes += fix_windows_binary(binary, app)
    return changes


def windows_main():
    app = sys.argv[1]
    while True:
        changes = windows_iteration(app)
        if changes == 0:
            break


if __name__ == "__main__":
    if sys.platform == "darwin":
        strip = True
        macos_main()
    elif sys.platform.startswith("win32"):
        strip = True
        windows_main()
    elif sys.platform.startswith("linux"):
        strip = True
        sys.argv.extend(["--rpath=$ORIGIN"])
        linux_main()

    if excluded_libraries:
        print("")
        for library in sorted(excluded_libraries.keys()):
            print("[FSBUILD] Exclude", library)
            for dependent in sorted(excluded_libraries[library]):
                print("  - depended on by", os.path.basename(dependent))
        # print("Included libraries:")
    if included_libraries:
        print("")
        for library in sorted(included_libraries.keys()):
            print("[FSBUILD] Include", os.path.basename(library))
            print("  - from", os.path.dirname(library))
            for dependent in sorted(included_libraries[library]):
                print("  - depended on by", os.path.basename(dependent))
    print("")
