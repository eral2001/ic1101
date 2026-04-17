import pytest


class RecordingInvoker:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def __call__(self, argv: list[str]) -> None:
        self.calls.append(argv)


@pytest.fixture
def recording_invoker() -> RecordingInvoker:
    return RecordingInvoker()
