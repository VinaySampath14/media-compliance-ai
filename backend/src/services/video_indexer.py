import os
import time
import logging
import requests
import yt_dlp
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("video-indexer")


class VideoIndexerService:

    def __init__(self):
        self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
        self.location = os.getenv("AZURE_VI_LOCATION")
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        self.vi_name = os.getenv("AZURE_VI_NAME")
        self.credential = DefaultAzureCredential()

    # ------------------------------------------------------------------ #
    # STEP 1 — AUTH
    # Azure VI uses two-step auth:
    #   ARM token  → proves you own the Azure subscription
    #   VI token   → proves you can use this specific VI account
    # ------------------------------------------------------------------ #

    def get_access_token(self):
        """Gets an ARM token from Azure Active Directory."""
        try:
            token = self.credential.get_token("https://management.azure.com/.default")
            return token.token
        except Exception as e:
            logger.error(f"Failed to get ARM token: {e}")
            raise

    def get_account_token(self, arm_token):
        """Exchanges ARM token for a Video Indexer account token."""
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"Bearer {arm_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get VI token: {response.text}")
        return response.json().get("accessToken")

    # ------------------------------------------------------------------ #
    # STEP 2 — DOWNLOAD
    # yt-dlp downloads the YouTube video to a local temp file
    # ------------------------------------------------------------------ #

    def download_youtube_video(self, url, output_path="temp_video.mp4"):
        """Downloads a YouTube video to a local file using yt-dlp."""
        logger.info(f"Downloading: {url}")

        ydl_opts = {
            "format": "best",
            "outtmpl": output_path,
            "quiet": False,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            logger.info("Download complete.")
            return output_path
        except Exception as e:
            raise Exception(f"YouTube download failed: {e}")

    # ------------------------------------------------------------------ #
    # STEP 3 — UPLOAD
    # Streams the local file to Azure VI
    # ------------------------------------------------------------------ #

    def upload_video(self, video_path, video_name):
        """Uploads a local video file to Azure Video Indexer."""
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"
        params = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default",
        }

        logger.info(f"Uploading {video_path} to Azure VI...")

        with open(video_path, "rb") as f:
            response = requests.post(url, params=params, files={"file": f})

        if response.status_code != 200:
            raise Exception(f"Upload failed: {response.text}")

        azure_video_id = response.json().get("id")
        logger.info(f"Upload success. Azure VI ID: {azure_video_id}")
        return azure_video_id

    # ------------------------------------------------------------------ #
    # STEP 4 — POLL
    # Azure VI processes async — we poll until done
    # FIX over YouTuber's version: added max_wait timeout (no infinite loop)
    # ------------------------------------------------------------------ #

    def wait_for_processing(self, video_id, max_wait_seconds=600):
        """
        Polls Azure VI every 30s until video is processed.
        Raises after max_wait_seconds to avoid infinite loops.
        """
        logger.info(f"Waiting for video {video_id} to process...")
        elapsed = 0

        while elapsed < max_wait_seconds:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)

            url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index"
            response = requests.get(url, params={"accessToken": vi_token})
            data = response.json()
            state = data.get("state")

            if state == "Processed":
                logger.info("Processing complete.")
                return data
            elif state == "Failed":
                raise Exception("Azure VI processing failed.")
            elif state == "Quarantined":
                raise Exception("Video quarantined — copyright or content policy violation.")

            logger.info(f"Status: {state}... waiting 30s (elapsed: {elapsed}s)")
            time.sleep(30)
            elapsed += 30

        raise Exception(f"Timeout — video not processed within {max_wait_seconds}s")

    # ------------------------------------------------------------------ #
    # STEP 5 — EXTRACT
    # Parse the Azure VI JSON into just what our state needs
    # ------------------------------------------------------------------ #

    def extract_data(self, vi_json):
        """Extracts transcript and OCR text from Azure VI response."""
        transcript_lines = []
        ocr_lines = []

        for video in vi_json.get("videos", []):
            insights = video.get("insights", {})

            for item in insights.get("transcript", []):
                transcript_lines.append(item.get("text", ""))

            for item in insights.get("ocr", []):
                ocr_lines.append(item.get("text", ""))

        return {
            "transcript": " ".join(transcript_lines),
            "ocr_text": ocr_lines,
            "video_metadata": {
                "duration": vi_json.get("summarizedInsights", {}).get("duration", {}).get("seconds"),
                "platform": "youtube"
            }
        }
