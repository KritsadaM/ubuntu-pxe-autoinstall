#!/bin/bash
set -e

CONFIG_FILE="/data/config.json"

SERVER_IP="${SERVER_IP:-192.168.1.100}"
HTTP_PORT="${HTTP_PORT:-8080}"
DHCP_MODE="${DHCP_MODE:-full}"
DHCP_RANGE_START="${DHCP_RANGE_START:-192.168.1.200}"
DHCP_RANGE_END="${DHCP_RANGE_END:-192.168.1.250}"
SUBNET_MASK="${SUBNET_MASK:-255.255.255.0}"
GATEWAY="${GATEWAY:-192.168.1.1}"
DNS_SERVERS="${DNS_SERVERS:-8.8.8.8,1.1.1.1}"

# If persistent config.json exists, read settings using python3
if [ -f "$CONFIG_FILE" ]; then
    echo "Loading existing configuration from $CONFIG_FILE..."
    SERVER_IP=$(python3 -c "import json; cfg=json.load(open('$CONFIG_FILE')); print(cfg.get('server_ip', '$SERVER_IP'))" 2>/dev/null || echo "$SERVER_IP")
    HTTP_PORT=$(python3 -c "import json; cfg=json.load(open('$CONFIG_FILE')); print(cfg.get('http_port', '$HTTP_PORT'))" 2>/dev/null || echo "$HTTP_PORT")
    DHCP_MODE=$(python3 -c "import json; cfg=json.load(open('$CONFIG_FILE')); print(cfg.get('dhcp_mode', '$DHCP_MODE'))" 2>/dev/null || echo "$DHCP_MODE")
    DHCP_RANGE_START=$(python3 -c "import json; cfg=json.load(open('$CONFIG_FILE')); print(cfg.get('dhcp_range_start', '$DHCP_RANGE_START'))" 2>/dev/null || echo "$DHCP_RANGE_START")
    DHCP_RANGE_END=$(python3 -c "import json; cfg=json.load(open('$CONFIG_FILE')); print(cfg.get('dhcp_range_end', '$DHCP_RANGE_END'))" 2>/dev/null || echo "$DHCP_RANGE_END")
    SUBNET_MASK=$(python3 -c "import json; cfg=json.load(open('$CONFIG_FILE')); print(cfg.get('subnet_mask', '$SUBNET_MASK'))" 2>/dev/null || echo "$SUBNET_MASK")
    GATEWAY=$(python3 -c "import json; cfg=json.load(open('$CONFIG_FILE')); print(cfg.get('gateway', '$GATEWAY'))" 2>/dev/null || echo "$GATEWAY")
    DNS_SERVERS=$(python3 -c "import json; cfg=json.load(open('$CONFIG_FILE')); d=cfg.get('dns', ['8.8.8.8','1.1.1.1']); print(','.join(d) if isinstance(d,list) else str(d))" 2>/dev/null || echo "$DNS_SERVERS")
fi

echo "=========================================================="
echo " Starting Ubuntu PXE Autoinstall Server"
echo " Server IP       : $SERVER_IP"
echo " HTTP Port       : $HTTP_PORT"
echo " DHCP Mode       : $DHCP_MODE"
if [ "$DHCP_MODE" = "full" ]; then
    echo " DHCP Range      : $DHCP_RANGE_START - $DHCP_RANGE_END"
    echo " Gateway         : $GATEWAY"
    echo " DNS Servers     : $DNS_SERVERS"
fi
echo "=========================================================="

# Ensure directories exist
mkdir -p /tftpboot /data/iso /data/netboot/ubuntu-24.04 /data/netboot/ubuntu-22.04 /data/netboot/ubuntu-20.04

# Ensure iPXE bootloaders exist in /tftpboot
if [ ! -f "/tftpboot/undionly.kpxe" ]; then
    echo "Downloading undionly.kpxe (BIOS bootloader)..."
    curl -sSL -o /tftpboot/undionly.kpxe http://boot.ipxe.org/undionly.kpxe || true
fi

if [ ! -f "/tftpboot/ipxe.efi" ]; then
    echo "Downloading ipxe.efi (UEFI bootloader)..."
    curl -sSL -o /tftpboot/ipxe.efi http://boot.ipxe.org/ipxe.efi || true
fi

# Build DHCP Config block
if [ "$DHCP_MODE" = "proxy" ]; then
    DHCP_BLOCK="dhcp-range=$SERVER_IP,proxy"
else
    DHCP_BLOCK="dhcp-range=$DHCP_RANGE_START,$DHCP_RANGE_END,$SUBNET_MASK,1h\ndhcp-option=3,$GATEWAY\ndhcp-option=6,$DNS_SERVERS"
fi

# Generate /etc/dnsmasq.conf from template
sed -e "s/{{SERVER_IP}}/$SERVER_IP/g" \
    -e "s/{{HTTP_PORT}}/$HTTP_PORT/g" \
    /etc/dnsmasq.conf.template > /etc/dnsmasq.conf

# Replace {{DHCP_CONFIG}} with multi-line block
python3 -c "
with open('/etc/dnsmasq.conf', 'r') as f:
    content = f.read()
block = '''$DHCP_BLOCK'''.replace('\\\\n', '\n')
content = content.replace('{{DHCP_CONFIG}}', block)
with open('/etc/dnsmasq.conf', 'w') as f:
    f.write(content)
"

echo "Dnsmasq configuration generated successfully."
echo "Starting services under Supervisord..."

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
