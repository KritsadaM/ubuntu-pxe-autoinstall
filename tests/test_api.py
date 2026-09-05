import pytest
from fastapi.testclient import TestClient
from app.main import app, DEFAULT_CONFIG


@pytest.fixture
def client():
    return TestClient(app)


def test_get_dashboard(client):
    """Test web dashboard HTML loading."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Ubuntu PXE Autoinstall Server" in response.text
    assert "text/html" in response.headers["content-type"]


def test_get_config(client):
    """Test GET /api/config endpoint."""
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "server_ip" in data
    assert "username" in data
    assert "dhcp_mode" in data


def test_post_config(client):
    """Test POST /api/config updating settings."""
    payload = {
        "server_ip": "10.10.10.5",
        "http_port": 8080,
        "dhcp_mode": "proxy",
        "dhcp_range_start": "10.10.10.100",
        "dhcp_range_end": "10.10.10.200",
        "subnet_mask": "255.255.255.0",
        "gateway": "10.10.10.1",
        "dns": ["1.1.1.1"],
        "hostname": "pxe-worker-01",
        "username": "deploy",
        "password": "NewSecretPass2026!",
        "realname": "Cluster Node Admin",
        "timezone": "UTC",
        "ssh_authorized_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAtestkey",
        "network_mode": "static",
        "static_ip": "10.10.10.55/24",
        "packages": ["curl", "wget", "docker.io"],
    }
    response = client.post("/api/config", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"

    # Verify updated in subsequent GET
    cfg = client.get("/api/config").json()
    assert cfg["hostname"] == "pxe-worker-01"
    assert cfg["username"] == "deploy"
    assert cfg["server_ip"] == "10.10.10.5"


def test_boot_ipxe_endpoint(client):
    """Test dynamic iPXE script generation."""
    response = client.get("/boot.ipxe")
    assert response.status_code == 200
    text = response.text
    assert text.startswith("#!ipxe")
    assert "menu Ubuntu Netboot PXE Autoinstall Server" in text
    assert "ub2404" in text
    assert "ub2204" in text
    assert "ub2004" in text
    assert "kernel ${server_url}/netboot/${os_dir}/vmlinuz" in text
    assert "initrd ${server_url}/netboot/${os_dir}/initrd" in text
    assert "autoinstall ds=nocloud-net;s=${server_url}/autoinstall/" in text


def test_subiquity_endpoints(client):
    """Test Subiquity cloud-init endpoints."""
    # Meta-data
    res_meta = client.get("/autoinstall/meta-data")
    assert res_meta.status_code == 200
    assert "instance-id:" in res_meta.text

    # User-data
    res_user = client.get("/autoinstall/user-data")
    assert res_user.status_code == 200
    assert res_user.text.startswith("#cloud-config")
    assert "autoinstall:" in res_user.text
    assert "password: '$6$" in res_user.text

    # Vendor-data
    res_vendor = client.get("/autoinstall/vendor-data")
    assert res_vendor.status_code == 200
    assert res_vendor.text == ""


def test_status_endpoint(client):
    """Test /api/status returning asset availability."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "ubuntu-24.04" in data
    assert "ubuntu-22.04" in data
    assert "ubuntu-20.04" in data
    assert "ready" in data["ubuntu-24.04"]
