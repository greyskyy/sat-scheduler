"""Utilities ensure orekit is properly initialize on subthreads."""
import orekit

import orekitfactory.initializer


def maybe_attach_thread():
    """Attach the current thread, if not already attached."""
    vm_env = orekit.getVMEnv()
    if not vm_env or not vm_env.isCurrentThreadAttached():
        vm = orekitfactory.initializer.get_orekit_vm()
        vm.attachCurrentThread()


def attach_orekit(func):
    """Ensure the attached function is attached to the JVM."""

    def wrapper(*args, **kwargs):
        maybe_attach_thread()
        return func(*args, **kwargs)

    return wrapper
