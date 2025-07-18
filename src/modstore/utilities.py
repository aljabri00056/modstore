import re
import requests
from pathlib import Path
from loguru import logger
from .models import Version, DyLib
from .udrop_client import UDropClient, UDropAPIError


def get_appstore_id(url: str) -> str:
    """
    Extracts the App Store ID from a given app URL.
    """
    m = re.search(r"id(\d+)\b", url)
    if m:
        return m.group(1)
    raise ValueError("Invalid app URL format.")


def get_app_info(url: str, country_code="sa") -> dict:
    """
    Fetches app information from the App Store.
    """
    url = f"https://itunes.apple.com/lookup?id={get_appstore_id(url)}&country={country_code}"
    req = requests.get(url)
    if not req.ok:
        raise Exception(
            f"Failed to fetch data from iTunes API: {req.status_code} {req.reason}")

    return req.json()['results'][0]


def get_latest_version_from_appstore(url: str, country_code="sa") -> Version:
    """
    Fetches the latest version of an app from the App Store.
    """

    app_data = get_app_info(url, country_code)

    return Version(
        version=app_data['version'],
        date=app_data['currentVersionReleaseDate'],
        description=app_data['releaseNotes'],
        size=app_data['fileSizeBytes'],
        minOSVersion=app_data['minimumOsVersion']
    )


def download_file_from_url(url: str, file_path: Path) -> Path:
    """Download a file from URL and save it locally."""
    response = requests.get(url)
    response.raise_for_status()

    file_path.write_bytes(response.content)
    logger.info(f"Downloaded file from {url} to {file_path}")
    return file_path


def download_dylibs(dylibs: list[DyLib]) -> list[str]:
    downloaded_paths = []
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    for dylib in dylibs:
        dest_filename = downloads_dir / Path(dylib.url).name
        try:
            downloaded_file = download_file_from_url(
                dylib.url, dest_filename)
            downloaded_paths.append(downloaded_file)
        except Exception as e:
            logger.error(f"Failed to download {dylib.url}: {e}")
            raise

    return downloaded_paths


def upload_app(file_path: str, new_name: str = None) -> str:
    """
    Uploads an app file to UDrop and returns the download URL.

    Args:
        file_path: Path to the file to upload
        new_name: Optional new name for the file (including extension)
    """
    file_path = Path(file_path)

    if new_name:
        new_file_path = file_path.parent / new_name
        file_path.rename(new_file_path)
        file_path = new_file_path

    try:
        with UDropClient() as client:
            download_url = client.upload_file(str(file_path), 938204)
            logger.info(f"File {file_path} uploaded successfully.")
            logger.info(f"Download URL: {download_url}")
            file_path.unlink()
            logger.info(f"Local file {file_path} deleted after upload.")
            return download_url
    except UDropAPIError as e:
        raise Exception(
            f"UDrop API Error: {e.message} (Status Code: {e.status_code})")
    except Exception as e:
        raise Exception(f"Unexpected error during upload: {e}")
