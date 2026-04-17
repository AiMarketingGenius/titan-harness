#!/usr/bin/env python3
"""Add n8n-worker service to docker-compose.yml by copying env from existing n8n service.
Usage: add_worker.py /opt/n8n/docker-compose.yml
"""
import sys
import copy
import yaml

path = sys.argv[1]
with open(path) as f:
    doc = yaml.safe_load(f)

if 'services' not in doc or 'n8n' not in doc['services']:
    print("ERROR: services.n8n not found", file=sys.stderr)
    sys.exit(2)

if 'n8n-worker' in doc['services']:
    print("INFO: n8n-worker already present, skipping", file=sys.stderr)
    sys.exit(0)

main = doc['services']['n8n']

# Clone env list, drop webhook-only vars
drop_prefixes = ('N8N_HOST=', 'N8N_PROTOCOL=', 'WEBHOOK_URL=')
env = [e for e in main.get('environment', []) if not e.startswith(drop_prefixes)]

worker = {
    'image': main.get('image', 'n8nio/n8n'),
    'restart': 'unless-stopped',
    'command': ['worker'],
    'environment': env,
}

# Copy extra_hosts if present (workers may need host-gateway for Ollama etc)
if 'extra_hosts' in main:
    worker['extra_hosts'] = copy.deepcopy(main['extra_hosts'])

# depends_on — only include service keys that exist in compose
deps = []
if 'n8n-redis' in doc['services']:
    deps.append('n8n-redis')
if 'n8n-postgres' in doc['services']:
    deps.append('n8n-postgres')
if deps:
    # simple list form
    worker['depends_on'] = deps

doc['services']['n8n-worker'] = worker

with open(path, 'w') as f:
    yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False, width=200)

print("OK: n8n-worker added")
