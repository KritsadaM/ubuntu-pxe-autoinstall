import os
import json
import glob
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.autoinstall import (
    generate_subiquity_userdata,
    generate_metadata,
    hash_password,
)

app = FastAPI(
    title="Ubuntu PXE Autoinstall Server",
    description="PXE Netboot & Subiquity Autoinstall for Ubuntu 20.04, 22.04, 24.04 LTS",
    version="1.0.0",
)

# Base Paths Configuration
DATA_DIR = os.environ.get("DATA_DIR", "/data" if os.path.exists("/data") else os.path.abspath("./data"))
CONFIG_PATH = os.environ.get("CONFIG_PATH", os.path.join(DATA_DIR, "config.json"))
ISO_DIR = os.environ.get("ISO_DIR", os.path.join(DATA_DIR, "iso"))
NETBOOT_DIR = os.environ.get("NETBOOT_DIR", os.path.join(DATA_DIR, "netboot"))
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# Ensure required runtime directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ISO_DIR, exist_ok=True)
os.makedirs(NETBOOT_DIR, exist_ok=True)
os.makedirs(os.path.join(NETBOOT_DIR, "ubuntu-24.04"), exist_ok=True)
os.makedirs(os.path.join(NETBOOT_DIR, "ubuntu-22.04"), exist_ok=True)
os.makedirs(os.path.join(NETBOOT_DIR, "ubuntu-20.04"), exist_ok=True)

# Mount Static Directories for Netboot Kernel/Initrd and ISOs
app.mount("/netboot", StaticFiles(directory=NETBOOT_DIR), name="netboot")
app.mount("/iso", StaticFiles(directory=ISO_DIR), name="iso")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

DEFAULT_CONFIG: Dict[str, Any] = {
    "server_ip": "192.168.1.100",
    "http_port": 8080,
    "dhcp_mode": "full",  # 'full' (stand-alone DHCP) or 'proxy' (ProxyDHCP)
    "dhcp_range_start": "192.168.1.200",
    "dhcp_range_end": "192.168.1.250",
    "subnet_mask": "255.255.255.0",
    "gateway": "192.168.1.1",
    "dns": ["8.8.8.8", "1.1.1.1"],
    "hostname": "ubuntu-node",
    "username": "ubuntu",
    "password": "Ubuntu2024!",
    "realname": "Ubuntu Administrator",
    "timezone": "Asia/Bangkok",
    "ssh_authorized_key": "",
    "network_mode": "dhcp",  # 'dhcp' or 'static'
    "static_ip": "192.168.1.150/24",
    "packages": ["curl", "wget", "git", "htop", "openssh-server", "vim"],
}


def load_config() -> Dict[str, Any]:
    """Loads configuration from persistent disk or returns defaults."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                return {**DEFAULT_CONFIG, **saved}
        except Exception as e:
            print(f"Warning: Failed to load config from {CONFIG_PATH}: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(cfg: Dict[str, Any]) -> None:
    """Saves configuration safely to disk."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


class ConfigSchema(BaseModel):
    server_ip: str
    http_port: int = 8080
    dhcp_mode: str = "full"
    dhcp_range_start: str = "192.168.1.200"
    dhcp_range_end: str = "192.168.1.250"
    subnet_mask: str = "255.255.255.0"
    gateway: str = "192.168.1.1"
    dns: List[str] = ["8.8.8.8", "1.1.1.1"]
    hostname: str = "ubuntu-node"
    username: str = "ubuntu"
    password: str = "Ubuntu2024!"
    realname: str = "Ubuntu Administrator"
    timezone: str = "Asia/Bangkok"
    ssh_authorized_key: Optional[str] = ""
    network_mode: str = "dhcp"
    static_ip: Optional[str] = "192.168.1.150/24"
    packages: List[str] = ["curl", "wget", "git", "htop", "openssh-server", "vim"]


def find_iso_file(version_prefix: str, default_name: str) -> str:
    """Finds an existing ISO matching the version prefix or returns default."""
    matches = glob.glob(os.path.join(ISO_DIR, f"{version_prefix}*.iso"))
    if matches:
        return os.path.basename(matches[0])
    return default_name


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Renders the main Web Configuration Dashboard."""
    cfg = load_config()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"config": cfg}
    )


@app.get("/api/config")
async def get_config():
    """Returns current configuration."""
    return JSONResponse(load_config())


@app.post("/api/config")
async def update_config(data: ConfigSchema):
    """Updates configuration and computes password hash."""
    cfg = data.model_dump()
    # Pre-hash password for fast generation
    cfg["password_hash"] = hash_password(cfg["password"])
    save_config(cfg)
    return JSONResponse({
        "status": "success",
        "message": "Configuration saved successfully",
        "config": cfg,
    })


@app.get("/api/status")
async def get_status():
    """Returns the ready status of ISOs and Netboot Kernels."""
    versions = {
        "ubuntu-24.04": {
            "iso_prefix": "ubuntu-24.04",
            "default_iso": "ubuntu-24.04-live-server-amd64.iso",
        },
        "ubuntu-22.04": {
            "iso_prefix": "ubuntu-22.04",
            "default_iso": "ubuntu-22.04-live-server-amd64.iso",
        },
        "ubuntu-20.04": {
            "iso_prefix": "ubuntu-20.04",
            "default_iso": "ubuntu-20.04-live-server-amd64.iso",
        },
    }

    result = {}
    for ver, meta in versions.items():
        iso_file = find_iso_file(meta["iso_prefix"], meta["default_iso"])
        iso_path = os.path.join(ISO_DIR, iso_file)
        iso_exists = os.path.isfile(iso_path)
        iso_size = os.path.getsize(iso_path) if iso_exists else 0

        vmlinuz_path = os.path.join(NETBOOT_DIR, ver, "vmlinuz")
        initrd_path = os.path.join(NETBOOT_DIR, ver, "initrd")

        vmlinuz_exists = os.path.isfile(vmlinuz_path)
        initrd_exists = os.path.isfile(initrd_path)

        result[ver] = {
            "iso_file": iso_file,
            "iso_exists": iso_exists,
            "iso_size_mb": round(iso_size / (1024 * 1024), 2) if iso_exists else 0,
            "kernel_ready": vmlinuz_exists and initrd_exists,
            "vmlinuz_exists": vmlinuz_exists,
            "initrd_exists": initrd_exists,
            "ready": iso_exists and vmlinuz_exists and initrd_exists,
        }

    return JSONResponse(result)


@app.get("/boot.ipxe", response_class=PlainTextResponse)
async def get_boot_ipxe():
    """Generates dynamic iPXE Boot Script with installation menu."""
    cfg = load_config()
    server_ip = cfg.get("server_ip", "192.168.1.100")
    port = cfg.get("http_port", 8080)
    server_url = f"http://{server_ip}:{port}"

    iso_24 = find_iso_file("ubuntu-24.04", "ubuntu-24.04-live-server-amd64.iso")
    iso_22 = find_iso_file("ubuntu-22.04", "ubuntu-22.04-live-server-amd64.iso")
    iso_20 = find_iso_file("ubuntu-20.04", "ubuntu-20.04-live-server-amd64.iso")

    ipxe_script = f"""#!ipxe

set server_url {server_url}

:start
menu Ubuntu Netboot PXE Autoinstall Server
item --gap --             ---------------- Ubuntu Versions ----------------
item ub2404              Install Ubuntu 24.04 LTS (Noble Numbat)
item ub2204              Install Ubuntu 22.04 LTS (Jammy Jellyfish)
item ub2004              Install Ubuntu 20.04 LTS (Focal Fossa)
item --gap --             ---------------- Maintenance --------------------
item local               Boot from local hard drive
item shell               Drop to iPXE interactive shell
item reboot              Reboot system

choose --default ub2404 --timeout 15000 target && goto ${{target}}

:ub2404
echo Starting Ubuntu 24.04 LTS Autoinstall...
set os_dir ubuntu-24.04
set iso_file {iso_24}
goto boot_ubuntu

:ub2204
echo Starting Ubuntu 22.04 LTS Autoinstall...
set os_dir ubuntu-22.04
set iso_file {iso_22}
goto boot_ubuntu

:ub2004
echo Starting Ubuntu 20.04 LTS Autoinstall...
set os_dir ubuntu-20.04
set iso_file {iso_20}
goto boot_ubuntu

:boot_ubuntu
echo Loading Linux Kernel...
kernel ${{server_url}}/netboot/${{os_dir}}/vmlinuz
echo Loading Initial Ramdisk...
initrd ${{server_url}}/netboot/${{os_dir}}/initrd
imgargs vmlinuz initrd=initrd ip=dhcp url=${{server_url}}/iso/${{iso_file}} autoinstall ds=nocloud-net;s=${{server_url}}/autoinstall/
echo Booting Ubuntu Subiquity Autoinstall...
boot

:local
echo Booting from local hard drive...
sanboot --no-describe --drive 0x80

:shell
echo Entering iPXE shell... Type 'exit' to return to menu.
shell
goto start

:reboot
reboot
"""
    return ipxe_script


# Subiquity Cloud-Init Endpoints
@app.get("/autoinstall/meta-data", response_class=PlainTextResponse)
async def get_metadata():
    """Serves Subiquity cloud-init instance metadata."""
    cfg = load_config()
    return generate_metadata(cfg)


@app.get("/autoinstall/user-data", response_class=PlainTextResponse)
async def get_userdata():
    """Serves dynamic Subiquity cloud-init user-data configuration."""
    cfg = load_config()
    return generate_subiquity_userdata(cfg)


@app.get("/autoinstall/vendor-data", response_class=PlainTextResponse)
async def get_vendordata():
    """Serves empty vendor-data for cloud-init."""
    return ""
