# ECS setup — exact commands used on the instance

Instance: Alibaba Cloud ECS, Singapore region, 4 vCPU / 8 GB (ecs.g7 class),
Ubuntu 24.04 LTS, 40 GB disk. VPC + public IP (pay-by-traffic).
Security group: 22 (home IP only), 80, 443 open; 8080 (home IP only until demo).
Key-pair login; password auth disabled.

## 1. Base packages

```bash
sudo apt-get update && sudo apt-get upgrade -y

# Docker + Compose plugin (official convenience script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# Python 3.11 (Ubuntu 24.04 ships 3.12; project pins 3.11)
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev git

# Node 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt-get install -y nodejs
```

## 2. Harden SSH (after confirming key login works)

```bash
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

## 3. Clone + configure

```bash
git clone https://github.com/Tanya-Khanna/engram.git
cd engram
cp .env.example .env
# then edit .env and set DASHSCOPE_API_KEY (pay-as-you-go sk- key)
```

## 4. Proof of deployment

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install openai
python deploy/alibaba_proof.py
```

## 5. Services

```bash
docker compose up -d
docker compose ps
```

⚠️ Do not release this instance until August 1 — judging runs July 10–31 and
judges may test live.
