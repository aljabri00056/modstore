from loguru import logger
import subprocess
from pathlib import Path
from src.modstore import AppsConfig
from src.modstore.utilities import get_latest_version_from_appstore, download_dylibs, upload_app, download_file_from_url
from src.modstore.decryptors import decrypt_app

apps_file = "apps.yaml"
apps_config = AppsConfig.from_yaml_file(apps_file)
logger.info(f"Loaded apps configuration from {apps_file}")

# check for updates
for app in apps_config.apps:
    logger.info(f"Processing app: {app.name}")
    try:
        latest_version = get_latest_version_from_appstore(str(app.store_url))
        logger.info(f"Latest version for {app.name}: {latest_version.version}")

        if not app.versions or app.versions[-1].version != latest_version.version:
            logger.info(
                f"Updating app {app.name} with new version {latest_version.version}")
            app.versions.insert(0, latest_version)
            apps_config.to_yaml_file(apps_file)

    except Exception as e:
        logger.error(f"Error processing {app.name}: {e}")

# decrypt and upload new versions
for app in apps_config.apps:
    if not app.versions[0].decrypted_url:
        logger.info(f"App {app.name} is not decrypted yet, processing...")

        try:
            decrypted_app = decrypt_app(str(app.store_url), timeout=120)
            logger.info(
                f"Decrypted app for {app.name}: {decrypted_app.file_path}")

        except Exception as e:
            logger.error(f"Error decrypting app {app.name}: {e}")
            continue

        if decrypted_app.version != app.versions[0].version:
            logger.warning(
                f"Decrypted version {decrypted_app.version} does not match latest version {app.versions[0].version} for {app.name}. Skipping upload.")
            continue

        try:
            download_url = upload_app(
                decrypted_app.file_path, new_name=f"{app.name}_{decrypted_app.version}_decrypted.ipa")
            logger.info(f"Uploaded app {app.name} to UDrop: {download_url}")
            app.versions[0].decrypted_url = download_url
            apps_config.to_yaml_file(apps_file)
        except Exception as e:
            logger.error(f"Error uploading app {app.name}: {e}")
            continue

        logger.info(f"Successfully decrypted and uploaded app {app.name}")

# tweak and upload tweaked versions
for app in apps_config.apps:
    if app.versions[0].decrypted_url and not app.versions[0].tweaked_url:
        logger.info(f"Tweaking app {app.name}...")

        logger.info(f"Processing dylibs for app: {app.name}")
        try:
            dylibs_paths = download_dylibs(app.dylibs)
            logger.info(f"Downloaded dylibs for {app.name}: {dylibs_paths}")
        except Exception as e:
            logger.error(f"Error processing dylibs for {app.name}: {e}")
            continue

        decrypted_filename = Path(
            f"downloads/{app.name}_{app.versions[0].version}_decrypted.ipa")
        try:
            download_file_from_url(
                app.versions[0].decrypted_url, decrypted_filename)
        except Exception as e:
            logger.error(
                f"Error downloading decrypted file for {app.name}: {e}")
            continue

        tweaked_filename = decrypted_filename.with_name(
            f"{app.name}_{app.versions[0].version}_tweaked.ipa")

        try:
            subprocess.run([
                "cyan",
                "-i", decrypted_filename,
                "-o", tweaked_filename,
                "-uwef", ",".join(dylibs_paths),
                "-n", app.name,
                "-b", app.bundle_id
            ], check=True)

            decrypted_filename.unlink(missing_ok=True)
            logger.info(
                f"Cleaned up downloaded decrypted file: {decrypted_filename}")

            for dylib_path in dylibs_paths:
                dylib_path.unlink(missing_ok=True)
            logger.info(f"Cleaned up downloaded dylibs: {dylibs_paths}")

        except subprocess.CalledProcessError as e:
            logger.error(
                f"Failed to tweak IPA for {app.name}: {e}")
            decrypted_filename.unlink(missing_ok=True)
            for dylib_path in dylibs_paths:
                dylib_path.unlink(missing_ok=True)
            continue

        logger.info(f"Uploading tweaked app {app.name}...")

        try:
            _, download_url = upload_app(tweaked_filename)
            logger.info(
                f"Uploaded tweaked app {app.name} to UDrop: {download_url}")
            app.versions[0].tweaked_url = download_url
            app.versions[0].size = tweaked_filename.stat().st_size
            apps_config.to_yaml_file(apps_file)
            tweaked_filename.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Error uploading tweaked app {app.name}: {e}")
            continue

        logger.info(f"Successfully processed tweaked app {app.name}")
