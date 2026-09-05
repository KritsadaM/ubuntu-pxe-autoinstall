"""
Subiquity Cloud-Init User-Data & Meta-Data Generator
Compatible with Ubuntu 20.04, 22.04, and 24.04 LTS Live Server
"""

import hashlib
import os
import secrets
from typing import Dict, Any, List, Optional


def _sha512_crypt_native(password: str, salt: Optional[str] = None, rounds: int = 5000) -> str:
    """
    Pure Python Ulrich Drepper standard glibc SHA-512 crypt implementation ($6$).
    Guarantees compatibility across any Python runtime without external C dependencies.
    """
    itoa64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    if salt is None:
        salt = "".join(secrets.choice(itoa64) for _ in range(16))
    else:
        # keep up to 16 valid characters
        salt = salt[:16]

    pwd_bytes = password.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    pwd_len = len(pwd_bytes)

    # Digest A
    ctx_a = hashlib.sha512(pwd_bytes + salt_bytes)
    ctx_b = hashlib.sha512(pwd_bytes + salt_bytes + pwd_bytes)
    alt_result = ctx_b.digest()

    for i in range(pwd_len, 0, -64):
        ctx_a.update(alt_result if i >= 64 else alt_result[:i])

    i = pwd_len
    while i > 0:
        if i & 1:
            ctx_a.update(alt_result)
        else:
            ctx_a.update(pwd_bytes)
        i >>= 1
    a_result = ctx_a.digest()

    # Digest P
    ctx_dp = hashlib.sha512()
    for _ in range(pwd_len):
        ctx_dp.update(pwd_bytes)
    dp = ctx_dp.digest()
    p = bytearray()
    for i in range(pwd_len, 0, -64):
        p.extend(dp if i >= 64 else dp[:i])

    # Digest S
    ctx_ds = hashlib.sha512()
    for _ in range(16 + a_result[0]):
        ctx_ds.update(salt_bytes)
    ds = ctx_ds.digest()
    s = bytearray()
    salt_len = len(salt_bytes)
    for i in range(salt_len, 0, -64):
        s.extend(ds if i >= 64 else ds[:i])

    # Rounds calculation
    c = a_result
    for r in range(rounds):
        ctx = hashlib.sha512()
        if r & 1:
            ctx.update(p)
        else:
            ctx.update(c)
        if r % 3 != 0:
            ctx.update(s)
        if r % 7 != 0:
            ctx.update(p)
        if r & 1:
            ctx.update(c)
        else:
            ctx.update(p)
        c = ctx.digest()

    def b64(b2: int, b1: int, b0: int, n: int) -> str:
        w = (b2 << 16) | (b1 << 8) | b0
        out = []
        for _ in range(n):
            out.append(itoa64[w & 0x3F])
            w >>= 6
        return "".join(out)

    order = [
        (0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4),
        (47, 5, 26), (6, 27, 48), (28, 49, 7), (50, 8, 29), (9, 30, 51),
        (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13), (56, 14, 35),
        (15, 36, 57), (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19),
        (62, 20, 41)
    ]
    res = []
    for idx2, idx1, idx0 in order:
        res.append(b64(c[idx2], c[idx1], c[idx0], 4))
    res.append(b64(0, 0, c[63], 2))
    encoded = "".join(res)

    if rounds == 5000:
        return f"$6${salt}${encoded}"
    return f"$6$rounds={rounds}${salt}${encoded}"


def hash_password(password: str) -> str:
    """
    Hashes a plain text password into Linux shadow $6$ (SHA-512) format.
    If already hashed, returns as-is.
    """
    if not password:
        password = "ubuntu"

    # If already a valid shadow hash
    if password.startswith(("$6$", "$y$", "$5$", "$1$", "$2b$", "$2a$")):
        return password

    try:
        from passlib.hash import sha512_crypt
        return sha512_crypt.using(rounds=5000).hash(password)
    except Exception:
        return _sha512_crypt_native(password, rounds=5000)


def generate_subiquity_userdata(cfg: Dict[str, Any]) -> str:
    """
    Generates user-data YAML compatible with Ubuntu Subiquity autoinstall.
    Works for 20.04, 22.04, and 24.04.
    """
    hostname = cfg.get("hostname", "ubuntu-node").strip() or "ubuntu-node"
    username = cfg.get("username", "ubuntu").strip() or "ubuntu"
    raw_pwd = cfg.get("password", "ubuntu")
    password_hash = hash_password(raw_pwd)
    realname = cfg.get("realname", "Ubuntu Administrator").strip() or "Ubuntu Administrator"
    timezone = cfg.get("timezone", "Asia/Bangkok").strip() or "Asia/Bangkok"
    ssh_key = (cfg.get("ssh_authorized_key") or "").strip()
    packages = cfg.get("packages", ["curl", "wget", "git", "htop", "openssh-server", "vim"])

    # Network configuration (Netplan version 2)
    net_mode = cfg.get("network_mode", "dhcp")
    if net_mode == "static":
        ip_addr = cfg.get("static_ip", "192.168.1.150/24").strip()
        gateway = cfg.get("gateway", "192.168.1.1").strip()
        dns_servers = cfg.get("dns", ["8.8.8.8", "1.1.1.1"])
        if isinstance(dns_servers, str):
            dns_servers = [d.strip() for d in dns_servers.split(",") if d.strip()]
        dns_str = ", ".join([f'"{d}"' for d in dns_servers])

        network_yaml = f"""  network:
    version: 2
    ethernets:
      main-interface:
        match:
          name: "en*"
        addresses:
          - {ip_addr}
        routes:
          - to: default
            via: {gateway}
        nameservers:
          addresses: [{dns_str}]"""
    else:
        network_yaml = """  network:
    version: 2
    ethernets:
      main-interface:
        match:
          name: "en*"
        dhcp4: true"""

    # SSH configuration
    ssh_keys_section = ""
    if ssh_key:
        ssh_keys_section = f"""    authorized-keys:
      - "{ssh_key}"\n"""

    # Extra packages
    if isinstance(packages, str):
        packages = [p.strip() for p in packages.split(",") if p.strip()]
    pkgs_yaml = "\n".join([f"    - {p}" for p in packages])

    yaml_content = f"""#cloud-config
autoinstall:
  version: 1
  refresh-installer:
    update: false
  locale: en_US.UTF-8
  keyboard:
    layout: us
  identity:
    hostname: {hostname}
    username: {username}
    password: '{password_hash}'
    realname: '{realname}'
{network_yaml}
  ssh:
    install-server: true
    allow-pw: true
{ssh_keys_section}  packages:
{pkgs_yaml}
  storage:
    layout:
      name: direct
  user-data:
    timezone: {timezone}
    disable_root: false
"""
    return yaml_content


def generate_metadata(cfg: Dict[str, Any]) -> str:
    """Generates cloud-init meta-data."""
    hostname = cfg.get("hostname", "ubuntu-node").strip() or "ubuntu-node"
    return f"instance-id: {hostname}\nlocal-hostname: {hostname}\n"
