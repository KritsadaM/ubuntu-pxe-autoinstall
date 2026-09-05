import pytest
from app.autoinstall import (
    hash_password,
    generate_subiquity_userdata,
    generate_metadata,
    _sha512_crypt_native,
)


def test_drepper_test_vector():
    """Verify that pure-python sha512_crypt matches Ulrich Drepper's glibc test vector."""
    # Drepper test vector: salt='saltstring', password='Hello world!'
    result = _sha512_crypt_native("Hello world!", salt="saltstring", rounds=5000)
    expected = "$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1"
    assert result == expected


def test_hash_password():
    """Verify password hashing."""
    # Plain text hash should start with $6$
    h = hash_password("MySecurePass123!")
    assert h.startswith("$6$")
    assert len(h) > 30

    # Already hashed password should not be re-hashed
    existing_hash = "$6$rounds=5000$saltsalt$hashedvalue1234567890"
    assert hash_password(existing_hash) == existing_hash

    # Yescrypt or other shadow prefix should not be re-hashed
    yescrypt_hash = "$y$j9T$saltsalt$hashedvalue"
    assert hash_password(yescrypt_hash) == yescrypt_hash


def test_generate_userdata_dhcp():
    """Verify Subiquity user-data generation in DHCP mode."""
    cfg = {
        "hostname": "ubuntu-pxe-node",
        "username": "sysadmin",
        "password": "Password123!",
        "realname": "System Administrator",
        "timezone": "Asia/Bangkok",
        "network_mode": "dhcp",
        "packages": ["curl", "wget", "git", "htop"],
    }
    content = generate_subiquity_userdata(cfg)

    assert content.startswith("#cloud-config")
    assert "autoinstall:" in content
    assert "version: 1" in content
    assert "hostname: ubuntu-pxe-node" in content
    assert "username: sysadmin" in content
    assert "password: '$6$" in content
    assert "dhcp4: true" in content
    assert "layout:\n      name: direct" in content
    assert "- curl" in content
    assert "- git" in content


def test_generate_userdata_static():
    """Verify Subiquity user-data generation in Static IP mode."""
    cfg = {
        "hostname": "node-static",
        "username": "admin",
        "password": "Password123!",
        "network_mode": "static",
        "static_ip": "192.168.1.150/24",
        "gateway": "192.168.1.1",
        "dns": ["8.8.8.8", "1.1.1.1"],
        "ssh_authorized_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG... user@host",
    }
    content = generate_subiquity_userdata(cfg)

    assert "hostname: node-static" in content
    assert "- 192.168.1.150/24" in content
    assert "via: 192.168.1.1" in content
    assert '"8.8.8.8", "1.1.1.1"' in content
    assert "authorized-keys:" in content
    assert "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG..." in content


def test_generate_metadata():
    """Verify metadata generation."""
    cfg = {"hostname": "my-server"}
    meta = generate_metadata(cfg)
    assert "instance-id: my-server" in meta
    assert "local-hostname: my-server" in meta
