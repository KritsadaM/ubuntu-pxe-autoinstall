FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies: dnsmasq, python3, pip, supervisor, curl, wget, p7zip
RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsmasq \
    python3 \
    python3-pip \
    supervisor \
    curl \
    wget \
    p7zip-full \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Create runtime directories
RUN mkdir -p /tftpboot /data/iso /data/netboot/ubuntu-24.04 /data/netboot/ubuntu-22.04 /data/netboot/ubuntu-20.04

# Pre-download iPXE binaries into TFTP root during build
RUN curl -sSL -o /tftpboot/undionly.kpxe http://boot.ipxe.org/undionly.kpxe || true && \
    curl -sSL -o /tftpboot/ipxe.efi http://boot.ipxe.org/ipxe.efi || true

# Copy Application Code and Configs
COPY app/ ./app/
COPY dnsmasq.conf.template /etc/dnsmasq.conf.template
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose Ports:
# - 67/udp: DHCP Server
# - 69/udp: TFTP Server
# - 8080/tcp: FastAPI Web Dashboard & ISO/iPXE File Server
EXPOSE 67/udp 69/udp 8080/tcp

ENTRYPOINT ["/entrypoint.sh"]
