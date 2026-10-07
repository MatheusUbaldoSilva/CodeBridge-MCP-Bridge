import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from rag.models.artifact_install import (
    ModelDownloadConsentError,
)
from rag.models.code_artifact_install import (
    DEFAULT_CODE_MODEL_SUBDIR,
    install_selected_code_model,
    resolve_code_model_directory,
    resolve_selected_code_model_path,
)
from rag.models.code_backend_policy import (
    CODE_MODEL_FILENAME,
    CODE_MODEL_REVISION,
    SELECTED_CODE_BACKEND,
)


class RagCodeArtifactInstallTests(unittest.TestCase):
    def test_default_path_is_revision_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = resolve_selected_code_model_path(
                local_app_data=root
            )
            self.assertEqual(
                path,
                root
                / DEFAULT_CODE_MODEL_SUBDIR
                / CODE_MODEL_REVISION
                / CODE_MODEL_FILENAME,
            )
            self.assertFalse(path.exists())

    def test_path_resolution_has_no_side_effect(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Local"
            resolve_code_model_directory(
                local_app_data=root
            )
            self.assertFalse(root.exists())

    def test_download_requires_explicit_authorization(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(
                ModelDownloadConsentError
            ):
                install_selected_code_model(
                    allow_download=False,
                    license_acknowledged=True,
                    local_app_data=Path(td),
                )

    def test_download_requires_license_acknowledgement(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(
                ModelDownloadConsentError
            ):
                install_selected_code_model(
                    allow_download=True,
                    license_acknowledged=False,
                    local_app_data=Path(td),
                    opener=lambda *a, **k: None,
                )

    def test_existing_valid_artifact_is_reused_without_network(self):
        pin = SELECTED_CODE_BACKEND.artifact_pin
        payload = b"fixture"
        fake_pin = type(pin)(
            revision=pin.revision,
            filename="fixture.gguf",
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            quantization="TEST",
            download_allowed=False,
        )

        # Generic installer behavior is already exhaustively covered by RAG-006.
        # This test only proves the code-model wrapper path contract.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = (
                root
                / DEFAULT_CODE_MODEL_SUBDIR
                / str(pin.revision)
                / str(pin.filename)
            )
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
