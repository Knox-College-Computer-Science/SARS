import logging
import httpx

logger = logging.getLogger(__name__)

# Fetch file bytes from Google Drive.
async def fetch_file_bytes(drive_file_id: str, access_token: str):
    async with httpx.AsyncClient() as client:
        meta_resp = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{drive_file_id}",
            params={"fields": "name,mimeType"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        meta_resp.raise_for_status()
        meta = meta_resp.json()

        dl_resp = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{drive_file_id}",
            params={"alt": "media"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        dl_resp.raise_for_status()

    return dl_resp.content, meta["name"]