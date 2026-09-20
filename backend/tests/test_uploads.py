"""Image upload: content type, size, filename safety, and role gate."""
import pytest

@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """Redirect uploads into a temp directory.

    Without this the tests would write real files into backend/uploads/ and
    accumulate them on every run.
    """
    monkeypatch.setattr('app.api.routes.UPLOAD_DIR', tmp_path)
    return tmp_path

# Minimal headers for each accepted type. The endpoint checks the declared
# content type AND the actual bytes, and rejects a mismatch — so a PNG upload
# needs PNG magic bytes, not the JPEG ones.
JPEG_BYTES = b'\xff\xd8\xff\xe0' + b'\x00' * 256
PNG_BYTES = b'\x89PNG\r\n\x1a\n' + b'\x00' * 256
WEBP_BYTES = b'RIFF' + b'\x00\x00\x00\x00' + b'WEBP' + b'\x00' * 256

def _upload(client, auth, user, content=JPEG_BYTES, filename='photo.jpg', content_type='image/jpeg'):
    return client.post(
        '/uploads',
        files={'file': (filename, content, content_type)},
        headers=auth(user),
    )

def test_farmer_can_upload_a_jpeg(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _upload(client, auth, farmer)

    assert r.status_code == 200
    body = r.json()
    assert body['url'].startswith('/uploads/')
    assert body['url'].endswith('.jpg')
    assert body['bytes'] == len(JPEG_BYTES)

def test_returned_url_is_relative_not_absolute(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    url = _upload(client, auth, farmer).json()['url']

    # Stored as a relative path so image_url stays environment-independent.
    assert not url.startswith('http')

def test_file_lands_on_disk_with_the_generated_name(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    url = _upload(client, auth, farmer).json()['url']
    stored = upload_dir / url.rsplit('/', 1)[-1]

    assert stored.exists()
    assert stored.read_bytes() == JPEG_BYTES

def test_client_filename_is_discarded(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _upload(client, auth, farmer, filename='../../../../etc/passwd.jpg')

    assert r.status_code == 200
    stored = upload_dir / r.json()['url'].rsplit('/', 1)[-1]
    # The generated name is a UUID hex plus extension, so traversal is impossible.
    assert stored.exists()
    assert 'passwd' not in stored.name
    assert '..' not in stored.name

def test_png_is_accepted(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _upload(client, auth, farmer, content=PNG_BYTES, content_type='image/png', filename='x.png')

    assert r.status_code == 200
    assert r.json()['url'].endswith('.png')

def test_webp_is_accepted(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _upload(client, auth, farmer, content=WEBP_BYTES, content_type='image/webp', filename='x.webp')

    assert r.status_code == 200
    assert r.json()['url'].endswith('.webp')

def test_gif_is_rejected(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _upload(client, auth, farmer, content_type='image/gif', filename='x.gif')

    assert r.status_code == 422

def test_pdf_is_rejected(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _upload(client, auth, farmer, content_type='application/pdf', filename='x.pdf')

    assert r.status_code == 422

def test_oversized_image_is_rejected(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')
    too_big = JPEG_BYTES + b'\x00' * (10 * 1024 * 1024)

    r = _upload(client, auth, farmer, content=too_big)

    assert r.status_code == 422
    assert '10 MB' in r.json()['detail']

def test_empty_file_is_rejected(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _upload(client, auth, farmer, content=b'')

    assert r.status_code == 422

def test_buyer_cannot_upload(client, auth, make_user, upload_dir):
    buyer = make_user('buyer@test.demo', 'buyer')

    r = _upload(client, auth, buyer)

    assert r.status_code == 403

def test_anonymous_cannot_upload(client, upload_dir):
    r = client.post('/uploads', files={'file': ('a.jpg', JPEG_BYTES, 'image/jpeg')})

    assert r.status_code == 401
