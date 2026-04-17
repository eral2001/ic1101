import asyncio
from pathlib import Path

from conftest import RecordingInvoker

from java.smali import Smali


class TestSmali:
    def test_assemble_builds_argv(self, recording_invoker: RecordingInvoker) -> None:
        smali = Smali(Path("/fake/smali.jar"), recording_invoker)

        asyncio.run(
            smali.assemble(
                input_dir=Path("/in/smali"),
                output_dex=Path("/out/classes.dex"),
            )
        )

        assert recording_invoker.calls == [
            [
                "java",
                "-jar",
                "/fake/smali.jar",
                "assemble",
                "/in/smali",
                "--output",
                "/out/classes.dex",
            ]
        ]
