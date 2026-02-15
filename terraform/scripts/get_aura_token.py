#!/usr/bin/env python3
"""
Get Neo4j Aura API OAuth token with caching.
"""
import sys
import json
import time
import os
from pathlib import Path
import requests

CACHE_FILE = Path.home() / '.cache' / 'neo4j-aura-token.json'
TOKEN_LIFETIME = 24 * 60 * 60  # 24 hours


def get_fresh_token(client_id, client_secret):
    """Get a fresh OAuth token from Neo4j Aura API."""
    response = requests.post(
        'https://api.neo4j.io/oauth/token',
        json={
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'audience': 'https://api.neo4j.io/'
        },
        timeout=30
    )

    if response.status_code != 200:
        print(f"Error getting token: {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        sys.exit(1)

    return response.json()['access_token']


def get_cached_token():
    """Get token from cache if valid."""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)

        # Check if token is still valid
        if time.time() - cache['timestamp'] < TOKEN_LIFETIME:
            return cache['token']
    except (json.JSONDecodeError, KeyError, IOError):
        pass

    return None


def cache_token(token):
    """Cache token to file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump({
            'token': token,
            'timestamp': time.time()
        }, f)


def main():
    """Main entry point."""
    # Get credentials from environment
    client_id = os.environ.get('TF_VAR_aura_client_id') or os.environ.get('AURA_CLIENT_ID')
    client_secret = os.environ.get('TF_VAR_aura_client_secret') or os.environ.get('AURA_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("Error: AURA_CLIENT_ID and AURA_CLIENT_SECRET must be set", file=sys.stderr)
        sys.exit(1)

    # Try cached token first
    token = get_cached_token()

    if not token:
        # Get fresh token
        token = get_fresh_token(client_id, client_secret)
        cache_token(token)

    # Output token
    print(token)


if __name__ == '__main__':
    main()
