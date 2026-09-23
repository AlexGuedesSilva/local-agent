from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.fixture
def isolated_temp_dir() -> Iterator[Path]:
    """Create an isolated temp directory owned by the current test process."""
    with TemporaryDirectory(prefix="local-agent-tests-") as directory:
        yield Path(directory)
