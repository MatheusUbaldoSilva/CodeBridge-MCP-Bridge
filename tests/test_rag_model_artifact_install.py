import hashlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.models.artifact_install import (
    DEFAULT_MODEL_SUBDIR,
    ModelArtifactIntegrityError,
    ModelDownloadConsentError,
    build_huggingface_artifact_url,
    install_verified_artifact,
    resolve_selected_model_path,
    verify_model_artifact,
)
from rag.models.backend_policy import (
    ModelArtifactPin,
    SELECTED_TEXT_BACKEND,
    TEXT_MODEL_FILENAME,
    TEXT_MODEL_QUANTIZATION,
    TEXT_MODEL_REVISION,
    TEXT_MODEL_SHA256,
    TEXT_MODEL_SIZE_BYTES,
    TEXT_RETRIEVAL_REPOSITORY,
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class RagModelArtifactInstallTests(unittest.TestCase):
    def fixture_artifact(self, payload: bytes) -> ModelArtifactPin:
        return ModelArtifactPin(
            revision="a" * 40,
            filename="fixture.gguf",
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            quantization="TEST",
            download_allowed=False,
        )

    def test_selected_artifact_is_fully_pinned(self):
        pin = SELECTED_TEXT_BACKEND.artifact_pin

        self.assertTrue(pin.is_fully_pinned)
        self.assertEqual(
            pin.revision,
            TEXT_MODEL_REVISION,
        )
        self.assertEqual(
            pin.filename,
            TEXT_MODEL_FILENAME,
        )
        self.assertEqual(
            pin.sha256,
            TEXT_MODEL_SHA256,
        )
        self.assertEqual(
            pin.size_bytes,
            TEXT_MODEL_SIZE_BYTES,
        )
        self.assertEqual(
            pin.quantization,
            TEXT_MODEL_QUANTIZATION,
        )
        self.assertFalse(pin.download_allowed)

    def test_pinned_values_match_rag_006_b_manifest(self):
        self.assertEqual(
            TEXT_MODEL_REVISION,
            "e9137ac0a9d41c851de69bea36babc029b7f5fc9",
        )
        self.assertEqual(
            TEXT_MODEL_FILENAME,
            "v5-small-retrieval-Q4_K_M.gguf",
        )
        self.assertEqual(
            TEXT_MODEL_SIZE_BYTES,
            396705152,
        )
        self.assertEqual(
            TEXT_MODEL_SHA256,
            "9440cf89f3e8a7a31a42e11b87e106dd5b344af4e0e3b6b21a96136cc8686e21",
        )
        self.assertEqual(
            TEXT_MODEL_QUANTIZATION,
            "Q4_K_M",
        )

    def test_download_url_uses_immutable_revision_not_main(self):
        url = build_huggingface_artifact_url(
            TEXT_RETRIEVAL_REPOSITORY,
            SELECTED_TEXT_BACKEND.artifact_pin,
        )

        self.assertIn(
            f"/resolve/{TEXT_MODEL_REVISION}/",
            url,
        )
        self.assertNotIn("/resolve/main/", url)

    def test_default_destination_is_revision_scoped_under_localappdata(self):
        path = resolve_selected_model_path(
            local_app_data=Path("C:/Users/test/AppData/Local"),
        )

        self.assertEqual(
            path,
            Path("C:/Users/test/AppData/Local")
            / DEFAULT_MODEL_SUBDIR
            / TEXT_MODEL_REVISION
            / TEXT_MODEL_FILENAME,
        )

    def test_import_or_path_resolution_does_not_create_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Local"
            path = resolve_selected_model_path(
                local_app_data=root,
            )

            self.assertFalse(root.exists())
            self.assertFalse(path.exists())

    def test_missing_artifact_verification_is_explicit(self):
        payload = b"fixture"
        pin = self.fixture_artifact(payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / pin.filename
            result = verify_model_artifact(
                path,
                pin,
            )

        self.assertFalse(result.exists)
        self.assertFalse(result.valid)
        self.assertIsNone(result.size_bytes)
        self.assertIsNone(result.sha256)

    def test_download_requires_explicit_allow_download(self):
        payload = b"fixture"
        pin = self.fixture_artifact(payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / pin.filename
            called = False

            def opener(*args, **kwargs):
                nonlocal called
                called = True
                return FakeResponse(payload)

            with self.assertRaises(
                ModelDownloadConsentError
            ):
                install_verified_artifact(
                    repository="owner/repo",
                    artifact=pin,
                    destination=path,
                    allow_download=False,
                    license_acknowledged=True,
                    opener=opener,
                )

            self.assertFalse(called)
            self.assertFalse(path.exists())

    def test_download_requires_license_acknowledgement(self):
        payload = b"fixture"
        pin = self.fixture_artifact(payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / pin.filename
            called = False

            def opener(*args, **kwargs):
                nonlocal called
                called = True
                return FakeResponse(payload)

            with self.assertRaises(
                ModelDownloadConsentError
            ):
                install_verified_artifact(
                    repository="owner/repo",
                    artifact=pin,
                    destination=path,
                    allow_download=True,
                    license_acknowledged=False,
                    opener=opener,
                )

            self.assertFalse(called)
            self.assertFalse(path.exists())

    def test_verified_download_is_atomic_and_hash_checked(self):
        payload = b"known fixture payload"
        pin = self.fixture_artifact(payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / pin.filename

            def opener(url, timeout):
                self.assertIn(
                    "/resolve/" + pin.revision + "/",
                    url,
                )
                self.assertEqual(timeout, 120)
                return FakeResponse(payload)

            result = install_verified_artifact(
                repository="owner/repo",
                artifact=pin,
                destination=path,
                allow_download=True,
                license_acknowledged=True,
                opener=opener,
            )

            self.assertTrue(result.downloaded)
            self.assertEqual(
                path.read_bytes(),
                payload,
            )
            self.assertFalse(
                path.with_name(
                    path.name + ".partial"
                ).exists()
            )

    def test_hash_mismatch_removes_partial_and_never_publishes_target(self):
        expected = b"expected"
        received = b"tampered!"
        pin = self.fixture_artifact(expected)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / pin.filename

            with self.assertRaises(
                ModelArtifactIntegrityError
            ):
                install_verified_artifact(
                    repository="owner/repo",
                    artifact=pin,
                    destination=path,
                    allow_download=True,
                    license_acknowledged=True,
                    opener=lambda *args, **kwargs: FakeResponse(
                        received
                    ),
                )

            self.assertFalse(path.exists())
            self.assertFalse(
                path.with_name(
                    path.name + ".partial"
                ).exists()
            )

    def test_size_overrun_fails_before_publish(self):
        expected = b"small"
        pin = self.fixture_artifact(expected)
        received = expected + b"extra"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / pin.filename

            with self.assertRaisesRegex(
                ModelArtifactIntegrityError,
                "exceeded",
            ):
                install_verified_artifact(
                    repository="owner/repo",
                    artifact=pin,
                    destination=path,
                    allow_download=True,
                    license_acknowledged=True,
                    opener=lambda *args, **kwargs: FakeResponse(
                        received
                    ),
                    chunk_size=2,
                )

            self.assertFalse(path.exists())

    def test_existing_valid_artifact_is_reused_without_network(self):
        payload = b"existing valid"
        pin = self.fixture_artifact(payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / pin.filename
            path.write_bytes(payload)

            def opener(*args, **kwargs):
                raise AssertionError(
                    "network must not be used"
                )

            result = install_verified_artifact(
                repository="owner/repo",
                artifact=pin,
                destination=path,
                allow_download=False,
                license_acknowledged=False,
                opener=opener,
            )

            self.assertFalse(result.downloaded)
            self.assertEqual(
                result.sha256,
                pin.sha256,
            )

    def test_existing_invalid_artifact_is_not_overwritten(self):
        payload = b"expected"
        pin = self.fixture_artifact(payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / pin.filename
            path.write_bytes(b"invalid")

            with self.assertRaisesRegex(
                ModelArtifactIntegrityError,
                "existing",
            ):
                install_verified_artifact(
                    repository="owner/repo",
                    artifact=pin,
                    destination=path,
                    allow_download=True,
                    license_acknowledged=True,
                    opener=lambda *args, **kwargs: FakeResponse(
                        payload
                    ),
                )

            self.assertEqual(
                path.read_bytes(),
                b"invalid",
            )

    def test_no_model_download_occurs_during_test_module_import(self):
        self.assertFalse(
            SELECTED_TEXT_BACKEND.auto_download_allowed
        )
        self.assertFalse(
            SELECTED_TEXT_BACKEND.artifact_pin.download_allowed
        )


if __name__ == "__main__":
    unittest.main()
