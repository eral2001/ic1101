from collections.abc import Awaitable, Callable

# A SubprocessInvoker is any async callable that takes an argv list and
# returns when the subprocess finishes (or raises if it failed).
SubprocessInvoker = Callable[[list[str]], Awaitable[None]]
