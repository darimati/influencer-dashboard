#!/usr/bin/env python3
"""
DARIMATI Creator Onboarding — One-Click Provisioning

Usage:
  python3 onboard.py --handle pink_seulgi --name 슬기
  python3 onboard.py --handle new_creator --name 크리에이터이름

What it does:
  1. Creates a Google Drive folder (@handle) with team sharing
  2. Generates NT parameter tracking link
  3. Saves to Supabase creator-profiles.json
  4. Updates Supabase pipeline.json
  5. Returns the personalized Creator Hub URL
"""

import argparse
import json
import sys
import time
import requests
from datetime import datetime, timezone

# === Config ===
SUPABASE_URL = 'https://chvxkfvimnqmmzsnyqrx.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNodnhrZnZpbW5xbW16c255cXJ4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDE2NjY3NiwiZXhwIjoyMDg1NzQyNjc2fQ.M8ptMiW7j5newWUPfEnptkPwry21ROiQXWEmSQNwIkw'
BUCKET = 'playbook-data'
PROFILES_PATH = 'sourcing/creator-profiles.json'
PIPELINE_PATH = 'sourcing/pipeline.json'

BASE_PRODUCT_URL = 'https://brand.naver.com/darimati/products/13462747167'
CREATOR_HUB_BASE = 'https://darimati.github.io/influencer-dashboard/creator.html'

SA_KEY_PATH = '/home/mayacrew/.hiper/credentials/google-service-account.json'

TEAM_SHARES = [
    {'email': 'jiun.kim@darimati.us', 'role': 'writer'},
    {'email': 'darimati.crew@gmail.com', 'role': 'writer'},
    {'email': 'dlgksruf1125@gmail.com', 'role': 'writer'},
    {'email': 'company@darimati.us', 'role': 'writer'},
    {'email': 'kaya991118@gmail.com', 'role': 'writer'},
]


def get_drive_token():
    """Get Google Drive access token via service account."""
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request

    creds = service_account.Credentials.from_service_account_file(
        SA_KEY_PATH, scopes=['https://www.googleapis.com/auth/drive']
    )
    creds.refresh(Request())
    return creds.token


def create_drive_folder(handle, drive_token):
    """Create a Google Drive folder for the creator and share with team."""
    headers = {
        'Authorization': f'Bearer {drive_token}',
        'Content-Type': 'application/json'
    }
    folder_name = f'@{handle}'

    # Check if folder already exists
    r = requests.get('https://www.googleapis.com/drive/v3/files', headers=headers, params={
        'q': f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        'fields': 'files(id,name,webViewLink)',
        'supportsAllDrives': 'true',
        'includeItemsFromAllDrives': 'true'
    })
    existing = r.json().get('files', [])
    if existing:
        link = existing[0].get('webViewLink', f"https://drive.google.com/drive/folders/{existing[0]['id']}")
        print(f'  Drive: EXISTS {link}')
        return link

    # Create folder
    r = requests.post('https://www.googleapis.com/drive/v3/files',
        headers=headers,
        json={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'},
        params={'supportsAllDrives': 'true', 'fields': 'id,webViewLink'})

    if r.status_code != 200:
        print(f'  Drive: FAIL {r.status_code}', file=sys.stderr)
        return None

    folder_id = r.json()['id']
    web_link = r.json().get('webViewLink', f'https://drive.google.com/drive/folders/{folder_id}')

    # Share: anyone with link = writer
    requests.post(f'https://www.googleapis.com/drive/v3/files/{folder_id}/permissions',
        headers=headers,
        json={'type': 'anyone', 'role': 'writer'},
        params={'supportsAllDrives': 'true'})

    # Share with team
    for member in TEAM_SHARES:
        requests.post(f'https://www.googleapis.com/drive/v3/files/{folder_id}/permissions',
            headers=headers,
            json={'type': 'user', 'role': member['role'], 'emailAddress': member['email']},
            params={'supportsAllDrives': 'true', 'sendNotificationEmail': 'false'})
        time.sleep(0.1)

    print(f'  Drive: CREATED {web_link}')
    return web_link


def build_nt_url(handle):
    """Build Naver Tracking URL."""
    detail = handle if handle.startswith('@') else f'@{handle}'
    params = f'nt_source=Insta&nt_medium=Creator&nt_detail={requests.utils.quote(detail)}&nt_keyword=June'
    return f'{BASE_PRODUCT_URL}?{params}'


def supa_read(path):
    """Read JSON from Supabase Storage."""
    r = requests.get(f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}',
        headers={'Authorization': f'Bearer {SUPABASE_KEY}', 'apikey': SUPABASE_KEY})
    return r.json() if r.status_code == 200 else None


def supa_write(path, data):
    """Write JSON to Supabase Storage (upsert)."""
    body = json.dumps(data)
    r = requests.post(f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}',
        headers={'Authorization': f'Bearer {SUPABASE_KEY}', 'apikey': SUPABASE_KEY,
                 'Content-Type': 'application/json', 'x-upsert': 'true'},
        data=body)
    if r.status_code == 400:
        r = requests.put(f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}',
            headers={'Authorization': f'Bearer {SUPABASE_KEY}', 'apikey': SUPABASE_KEY,
                     'Content-Type': 'application/json'},
            data=body)
    return r.status_code in (200, 201)


def onboard(handle, name, campaign='June'):
    """Full onboarding: Drive + NT + Supabase + URL."""
    now = datetime.now(timezone.utc).isoformat()
    print(f'\n=== Onboarding @{handle} ({name}) ===\n')

    # 1. Drive folder
    print('[1/4] Creating Drive folder...')
    drive_token = get_drive_token()
    drive_link = create_drive_folder(handle, drive_token)

    # 2. NT link
    print('[2/4] Generating NT link...')
    nt_link = build_nt_url(handle)
    print(f'  NT: {nt_link}')

    # 3. Update creator-profiles.json
    print('[3/4] Saving to creator-profiles...')
    profiles = supa_read(PROFILES_PATH) or {}
    profiles[handle] = {
        'handle': handle,
        'name': name,
        'driveLink': drive_link or '',
        'ntLink': nt_link,
        'campaign': campaign,
        'onboardedAt': now,
        'updatedAt': now
    }
    ok = supa_write(PROFILES_PATH, profiles)
    print(f'  Profiles: {"OK" if ok else "FAIL"}')

    # 4. Update pipeline.json
    print('[4/4] Updating pipeline...')
    pipeline = supa_read(PIPELINE_PATH) or {'pipeline': {}}
    if 'pipeline' not in pipeline:
        pipeline['pipeline'] = {}

    if handle not in pipeline['pipeline']:
        pipeline['pipeline'][handle] = {}

    pipeline['pipeline'][handle].update({
        'driveLink': drive_link or '',
        'updatedAt': now
    })
    pipeline['updatedAt'] = now
    ok2 = supa_write(PIPELINE_PATH, pipeline)
    print(f'  Pipeline: {"OK" if ok2 else "FAIL"}')

    # Build personalized URL
    from urllib.parse import quote
    guide_url = f'{CREATOR_HUB_BASE}?id={quote(handle)}&name={quote(name)}'

    print(f'\n=== DONE ===')
    print(f'Guide URL: {guide_url}')
    print(f'Drive:     {drive_link or "(failed)"}')
    print(f'NT Link:   {nt_link}')

    return {
        'handle': handle,
        'name': name,
        'guide_url': guide_url,
        'drive_link': drive_link,
        'nt_link': nt_link,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DARIMATI Creator Onboarding')
    parser.add_argument('--handle', required=True, help='Instagram handle (without @)')
    parser.add_argument('--name', required=True, help='Creator display name')
    parser.add_argument('--campaign', default='June', help='Campaign name (default: June)')
    args = parser.parse_args()

    result = onboard(args.handle, args.name, args.campaign)
    print(f'\n📋 Copy this URL for the creator:\n{result["guide_url"]}')
