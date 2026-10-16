import io
import time
from urllib.parse import parse_qs, urlparse

import pytest

from app.core import storage as storage_module
from app.core.storage import LocalStorage, S3Storage, StorageError, validate_key
from tests.conftest import get_client


@pytest.fixture
def local(tmp_path, monkeypatch):
    store = LocalStorage(tmp_path)
    monkeypatch.setattr(storage_module, "get_storage", lambda: store)
    monkeypatch.setattr("app.api.routes.health.get_storage", lambda: store)
    return store


def test_local_put_get_delete(local):
    local.put("exports/1/a.zip", b"hello")
    assert local.get("exports/1/a.zip") == b"hello"
    local.delete("exports/1/a.zip")
    with pytest.raises(StorageError):
        local.get("exports/1/a.zip")


@pytest.mark.parametrize("key", ["../etc/passwd", "a/../../b", "/abs", "dir/", "", "a b"])
def test_bad_keys_are_rejected(key):
    with pytest.raises(StorageError):
        validate_key(key)


def test_signed_download_link_works_and_expires(local):
    local.put("exports/1/data.zip", b"zip-bytes")
    client = get_client()
    url = urlparse(local.download_url("exports/1/data.zip", filename="my-data.zip"))
    response = client.get(f"{url.path}?{url.query}")
    assert response.status_code == 200
    assert response.content == b"zip-bytes"
    assert "my-data.zip" in response.headers["content-disposition"]

    params = parse_qs(url.query)
    tampered = client.get(
        f"{url.path}?expires={params['expires'][0]}&filename=other.zip&sig={params['sig'][0]}"
    )
    assert tampered.status_code == 403
    expired = client.get(
        f"{url.path}?expires={int(time.time()) - 10}&filename=my-data.zip&sig={params['sig'][0]}"
    )
    assert expired.status_code == 403


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(("put", kwargs))
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return f"https://bucket.example/{Params['Key']}?expires={ExpiresIn}&cd={Params.get('ResponseContentDisposition', '')}"


def test_s3_storage_encrypts_and_presigns():
    fake = FakeS3()
    store = S3Storage(fake, "leadsgen-files")
    store.put("exports/2/x.zip", b"data", "application/zip")
    assert fake.calls[0][1]["ServerSideEncryption"] == "AES256"
    assert store.get("exports/2/x.zip") == b"data"
    url = store.download_url("exports/2/x.zip", expires_in=600, filename="x.zip")
    assert "expires=600" in url and 'filename="x.zip"' in url
    store.delete("exports/2/x.zip")
    assert fake.objects == {}
