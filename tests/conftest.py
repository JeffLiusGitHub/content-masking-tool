import importlib.util

import pytest

NER_MODEL = "en_core_web_sm"
ner_available = importlib.util.find_spec(NER_MODEL) is not None

requires_ner = pytest.mark.skipif(
    not ner_available, reason=f"NER model {NER_MODEL} not installed"
)


@pytest.fixture
def vaults_dir(tmp_path):
    d = tmp_path / "vaults"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def isolated_masked_output_dir(tmp_path, monkeypatch):
    """Keep masked outputs out of the real Documents\\Masked Files folder."""
    d = tmp_path / "masked-output"
    monkeypatch.setenv("MASKINGTOOL_MASKED_DIR", str(d))
    return d
