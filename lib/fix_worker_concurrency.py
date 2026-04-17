#!/usr/bin/env python3
"""Set n8n-worker command to pass --concurrency=70 explicitly."""
import sys, yaml
path = sys.argv[1]
with open(path) as f:
    doc = yaml.safe_load(f)
w = doc['services'].get('n8n-worker')
if not w:
    print('ERROR: no n8n-worker service'); sys.exit(2)
w['command'] = ['worker', '--concurrency=70']
with open(path, 'w') as f:
    yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False, width=200)
print('OK: concurrency=70 set')
