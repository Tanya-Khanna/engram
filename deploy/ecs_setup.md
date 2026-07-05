# ECS setup — exact commands used on the instance

Instance: Alibaba Cloud ECS, Singapore region, 4 vCPU / 8 GB (ecs.g7 class),
Ubuntu 24.04 LTS, 40 GB disk. VPC + public IP (pay-by-traffic).
Security group: 22 (home IP only), 80, 443 open; 8080 (home IP only until demo).
Key-pair login; password auth disabled.

> Fill in each block below with the commands actually run, as they are run.
> This file is a judged artifact — it must reproduce the instance.

## 1. Base packages

```bash
# TODO: paste exact commands (Docker + Compose plugin per hackathon resource
# doc, Python 3.11, git, Node 20)
```

## 2. Clone + configure

```bash
git clone https://github.com/<user>/engram.git
cd engram
cp .env.example .env   # then set DASHSCOPE_API_KEY
```

## 3. Proof of deployment

```bash
python3 deploy/alibaba_proof.py
```

## 4. Services

```bash
docker compose up -d
docker compose ps
```

⚠️ Do not release this instance until August 1 — judging runs July 10–31 and
judges may test live.
