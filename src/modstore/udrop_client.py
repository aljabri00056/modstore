import requests
import json
import os
from typing import Optional, Any
import hashlib
import dotenv

dotenv.load_dotenv()


class UDropAPIError(Exception):
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class UDropClient:
    """
    Python client for the uDrop File Upload API

    This client provides a complete interface to the uDrop API for file management,
    including upload, download, folder operations, and account management.
    """

    def __init__(self, key1: Optional[str] = None, key2: Optional[str] = None, base_url: str = "https://www.udrop.com/api/v2/"):
        """
        Initialize the uDrop client

        Args:
            key1: API key 1 (64 characters). If None, will try to load from UDROP_API_KEY1 env var
            key2: API key 2 (64 characters). If None, will try to load from UDROP_API_KEY2 env var
            base_url: Base URL for API requests. Can be overridden with UDROP_BASE_URL env var
        """
        self.key1 = key1 or os.getenv('UDROP_API_KEY1')
        self.key2 = key2 or os.getenv('UDROP_API_KEY2')
        self.base_url = os.getenv('UDROP_BASE_URL', base_url).rstrip('/')

        if not self.key1 or not self.key2:
            raise UDropAPIError(
                "API keys not provided. Set UDROP_API_KEY1 and UDROP_API_KEY2 environment variables or pass them as arguments.")

        if len(self.key1) != 64 or len(self.key2) != 64:
            raise UDropAPIError("API keys must be exactly 64 characters long.")

        self.access_token: Optional[str] = None
        self.account_id: Optional[str] = None
        self.session = requests.Session()

    def _make_request(self, endpoint: str, data: dict[str, Any] = None, files: dict[str, Any] = None) -> dict[str, Any]:
        """
        Make a POST request to the API

        Args:
            endpoint: API endpoint (without base URL)
            data: Form data to send
            files: Files to upload

        Returns:
            Parsed JSON response

        Raises:
            UDropAPIError: If the request fails or returns an error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.post(url, data=data, files=files)
            response.raise_for_status()

            result = response.json()

            # Check if the API returned an error
            if result.get('_status') == 'error':
                raise UDropAPIError(result.get(
                    'response', 'Unknown error'), response.status_code)

            return result

        except requests.exceptions.RequestException as e:
            raise UDropAPIError(f"Request failed: {str(e)}")
        except json.JSONDecodeError:
            raise UDropAPIError("Invalid JSON response received")

    def authorize(self) -> dict[str, Any]:
        """
        Authenticate with the API and get access token

        Returns:
            dictionary containing access_token and account_id
        """
        data = {
            'key1': self.key1,
            'key2': self.key2
        }

        result = self._make_request('authorize', data)

        if 'data' in result:
            self.access_token = result['data']['access_token']
            self.account_id = result['data']['account_id']

        return result

    def disable_access_token(self) -> dict[str, Any]:
        """
        Disable the current access token

        Returns:
            API response
        """
        if not self.access_token or not self.account_id:
            raise UDropAPIError("Not authenticated. Call authorize() first.")

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id
        }

        result = self._make_request('disable_access_token', data)

        # Clear stored credentials
        self.access_token = None
        self.account_id = None

        return result

    def _ensure_authenticated(self):
        """Ensure we have valid authentication"""
        if not self.access_token or not self.account_id:
            raise UDropAPIError("Not authenticated. Call authorize() first.")

    def get_account_info(self) -> dict[str, Any]:
        """
        Get account information

        Returns:
            Account details including username, email, etc.
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id
        }

        return self._make_request('account/info', data)

    def get_account_package(self) -> dict[str, Any]:
        """
        Get account package information and restrictions

        Returns:
            Package details including limits and permissions
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id
        }

        return self._make_request('account/package', data)

    def upload_file(self, file_path: str, folder_id: Optional[str] = None) -> dict[str, Any]:
        """
        Upload a file

        Args:
            file_path: Path to the file to upload
            folder_id: Optional folder ID to upload to

        Returns:
            Upload response with file details
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id
        }

        if folder_id:
            data['folder_id'] = folder_id

        with open(file_path, 'rb') as f:
            files = {'upload_file': f}
            req = self._make_request('file/upload', data, files)
            short_url = req['data'][0]['short_url']
            return self.download_file(short_url=short_url)['data']['download_url']

    def download_file(self, file_id: Optional[str] = None, short_url: Optional[str] = None) -> dict[str, Any]:
        """
        Generate a download URL for a file

        Args:
            file_id: Numeric file ID
            short_url: Short URL of the file

        Returns:
            Download URL and file details
        """
        self._ensure_authenticated()

        if not file_id and not short_url:
            raise UDropAPIError("Either file_id or short_url must be provided")

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id
        }

        if file_id:
            data['file_id'] = file_id
        if short_url:
            data['short_url'] = short_url

        return self._make_request('file/download', data)

    def get_file_info(self, file_id: str) -> dict[str, Any]:
        """
        Get file information

        Args:
            file_id: File ID to get information for

        Returns:
            File metadata and URLs
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id,
            'file_id': file_id
        }

        return self._make_request('file/info', data)

    def edit_file(self, file_id: str, filename: Optional[str] = None,
                  file_type: Optional[str] = None, folder_id: Optional[str] = None) -> dict[str, Any]:
        """
        Edit file properties

        Args:
            file_id: File ID to edit
            filename: New filename (optional)
            file_type: New file type/mime type (optional)
            folder_id: New folder ID (optional)

        Returns:
            Updated file information
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id,
            'file_id': file_id
        }

        if filename:
            data['filename'] = filename
        if file_type:
            data['fileType'] = file_type
        if folder_id:
            data['folder_id'] = folder_id

        return self._make_request('file/edit', data)

    def delete_file(self, file_id: str) -> dict[str, Any]:
        """
        Delete a file

        Args:
            file_id: File ID to delete

        Returns:
            Deletion confirmation
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id,
            'file_id': file_id
        }

        return self._make_request('file/delete', data)

    def move_file(self, file_id: str, new_parent_folder_id: str) -> dict[str, Any]:
        """
        Move a file to another folder

        Args:
            file_id: File ID to move
            new_parent_folder_id: Destination folder ID

        Returns:
            Move confirmation
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id,
            'file_id': file_id,
            'new_parent_folder_id': new_parent_folder_id
        }

        return self._make_request('file/move', data)

    def copy_file(self, file_id: str, copy_to_folder_id: str) -> dict[str, Any]:
        """
        Copy a file to another folder

        Args:
            file_id: File ID to copy
            copy_to_folder_id: Destination folder ID

        Returns:
            Copy confirmation with original and new file info
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id,
            'file_id': file_id,
            'copy_to_folder_id': copy_to_folder_id
        }

        return self._make_request('file/copy', data)

    def create_folder(self, folder_name: str, parent_id: Optional[str] = None,
                      is_public: int = 0, access_password: Optional[str] = None) -> dict[str, Any]:
        """
        Create a new folder

        Args:
            folder_name: Name for the new folder
            parent_id: Parent folder ID (optional)
            is_public: 0=Private, 1=Unlisted, 2=Public (default: 0)
            access_password: Password for folder access (will be MD5 hashed)

        Returns:
            New folder information
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id,
            'folder_name': folder_name,
            'is_public': str(is_public)
        }

        if parent_id:
            data['parent_id'] = parent_id
        if access_password:
            data['access_password'] = hashlib.md5(
                access_password.encode()).hexdigest()

        return self._make_request('folder/create', data)

    def get_folder_listing(self, parent_folder_id: Optional[str] = None) -> dict[str, Any]:
        """
        Get folder and file listing

        Args:
            parent_folder_id: Parent folder ID (optional, defaults to root)

        Returns:
            List of folders and files
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id
        }

        if parent_folder_id:
            data['parent_folder_id'] = parent_folder_id

        return self._make_request('folder/listing', data)

    def get_folder_info(self, folder_id: str) -> dict[str, Any]:
        """
        Get folder information

        Args:
            folder_id: Folder ID to get information for

        Returns:
            Folder metadata
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id,
            'parent_folder_id': folder_id
        }

        return self._make_request('folder/info', data)

    def edit_folder(self, folder_id: str, folder_name: Optional[str] = None,
                    parent_id: Optional[str] = None, is_public: Optional[int] = None,
                    access_password: Optional[str] = None) -> dict[str, Any]:
        """
        Edit folder properties

        Args:
            folder_id: Folder ID to edit
            folder_name: New folder name (optional)
            parent_id: New parent folder ID (optional)
            is_public: 0=Private, 1=Unlisted, 2=Public (optional)
            access_password: New access password (optional, will be MD5 hashed)

        Returns:
            Updated folder information
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id,
            'folder_id': folder_id
        }

        if folder_name:
            data['folder_name'] = folder_name
        if parent_id:
            data['parent_id'] = parent_id
        if is_public is not None:
            data['is_public'] = str(is_public)
        if access_password:
            data['access_password'] = hashlib.md5(
                access_password.encode()).hexdigest()

        return self._make_request('folder/edit', data)

    def delete_folder(self, folder_id: str) -> dict[str, Any]:
        """
        Delete a folder

        Args:
            folder_id: Folder ID to delete

        Returns:
            Deletion confirmation
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id,
            'folder_id': folder_id
        }

        return self._make_request('folder/delete', data)

    def move_folder(self, folder_id: str, new_parent_folder_id: str) -> dict[str, Any]:
        """
        Move a folder to another location

        Args:
            folder_id: Folder ID to move
            new_parent_folder_id: Destination parent folder ID

        Returns:
            Move confirmation
        """
        self._ensure_authenticated()

        data = {
            'access_token': self.access_token,
            'account_id': self.account_id,
            'folder_id': folder_id,
            'new_parent_folder_id': new_parent_folder_id
        }

        return self._make_request('folder/move', data)

    def __enter__(self):
        """Context manager entry"""
        self.authorize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.access_token:
            try:
                self.disable_access_token()
            except Exception:
                pass  # Ignore errors during cleanup
