import json
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from typing import Union
from urllib.parse import urlparse

import pandas as pd


LOCAL_RUNS_URI = "outputs/runs"
INPUT_ARTIFACT = "input.csv"
RECOMMENDATIONS_ARTIFACT = "recommendations.parquet"
SUMMARY_ARTIFACT = "summary.json"


PathLike = Union[str, Path]


def run_artifact_uri(run_id: str, base_uri: PathLike = LOCAL_RUNS_URI) -> str:
    base = str(base_uri).rstrip("/")
    if base.startswith("s3://"):
        return f"{base}/{run_id}"
    return str(Path(base) / run_id)


def local_run_dir(run_id: str, base_dir: Path = Path(LOCAL_RUNS_URI)) -> Path:
    return Path(run_artifact_uri(run_id, base_dir))


def artifact_display_uri(uri: PathLike) -> str:
    return str(uri)


def artifact_uri(root_uri: PathLike, name: str) -> str:
    root = str(root_uri).rstrip("/")
    if root.startswith("s3://"):
        return f"{root}/{name}"
    return str(Path(root) / name)


def write_input_csv(input_df: pd.DataFrame, run_uri: PathLike) -> None:
    buffer = StringIO()
    input_df.to_csv(buffer, index=False)
    artifact_store(run_uri).write_bytes(
        INPUT_ARTIFACT,
        buffer.getvalue().encode("utf-8"),
    )


def read_input_csv(input_uri: PathLike) -> pd.DataFrame:
    uri = str(input_uri)
    if uri.startswith("s3://"):
        return pd.read_csv(BytesIO(read_uri_bytes(uri)))
    return pd.read_csv(Path(uri))


def write_pipeline_outputs(
    recommendations: pd.DataFrame,
    summary: dict,
    output_uri: PathLike,
) -> None:
    store = artifact_store(output_uri)

    parquet_buffer = BytesIO()
    recommendations.to_parquet(parquet_buffer, index=False)
    store.write_bytes(RECOMMENDATIONS_ARTIFACT, parquet_buffer.getvalue())
    store.write_bytes(
        SUMMARY_ARTIFACT,
        json.dumps(summary, indent=2).encode("utf-8"),
    )


def load_pipeline_outputs(output_uri: PathLike) -> tuple[pd.DataFrame, dict]:
    store = artifact_store(output_uri)
    recommendations = pd.read_parquet(BytesIO(store.read_bytes(RECOMMENDATIONS_ARTIFACT)))
    summary = json.loads(store.read_bytes(SUMMARY_ARTIFACT).decode("utf-8"))
    return recommendations, summary


def pipeline_outputs_exist(output_uri: PathLike) -> bool:
    store = artifact_store(output_uri)
    return store.exists(RECOMMENDATIONS_ARTIFACT) and store.exists(SUMMARY_ARTIFACT)


def read_uri_bytes(uri: str) -> bytes:
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        return S3ArtifactStore.from_uri(uri).read_root_bytes()
    return Path(uri).read_bytes()


def artifact_store(root_uri: PathLike) -> "ArtifactStore":
    uri = str(root_uri)
    if uri.startswith("s3://"):
        return S3ArtifactStore.from_uri(uri)
    return LocalArtifactStore(Path(uri))


class ArtifactStore:
    def read_bytes(self, name: str) -> bytes:
        raise NotImplementedError

    def write_bytes(self, name: str, content: bytes) -> None:
        raise NotImplementedError

    def exists(self, name: str) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class LocalArtifactStore(ArtifactStore):
    root: Path

    def read_bytes(self, name: str) -> bytes:
        return (self.root / name).read_bytes()

    def write_bytes(self, name: str, content: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / name).write_bytes(content)

    def exists(self, name: str) -> bool:
        return (self.root / name).exists()


@dataclass(frozen=True)
class S3ArtifactStore(ArtifactStore):
    bucket: str
    prefix: str

    @classmethod
    def from_uri(cls, uri: str) -> "S3ArtifactStore":
        parsed = urlparse(uri)
        if parsed.scheme != "s3" or not parsed.netloc:
            raise ValueError(f"Invalid S3 URI: {uri}")
        return cls(parsed.netloc, parsed.path.lstrip("/"))

    def read_root_bytes(self) -> bytes:
        return self._client().get_object(Bucket=self.bucket, Key=self.prefix)["Body"].read()

    def read_bytes(self, name: str) -> bytes:
        return self._client().get_object(Bucket=self.bucket, Key=self._key(name))["Body"].read()

    def write_bytes(self, name: str, content: bytes) -> None:
        self._client().put_object(Bucket=self.bucket, Key=self._key(name), Body=content)

    def exists(self, name: str) -> bool:
        try:
            self._client().head_object(Bucket=self.bucket, Key=self._key(name))
            return True
        except Exception as exc:
            if self._is_not_found(exc):
                return False
            raise

    def _key(self, name: str) -> str:
        if not self.prefix:
            return name
        return f"{self.prefix.rstrip('/')}/{name}"

    @staticmethod
    def _client():
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError(
                "S3 artifact storage requires boto3. Install project dependencies with uv sync."
            ) from exc
        return boto3.client("s3")

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        response = getattr(exc, "response", {})
        code = response.get("Error", {}).get("Code")
        return code in {"404", "NoSuchKey", "NotFound"}
