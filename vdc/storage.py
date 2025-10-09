"""
Google Cloud Storage service for browsing and managing files.
"""
from google.cloud import storage
from google.cloud.exceptions import NotFound, Forbidden
from config import Config
import os


class GCSStorageService:
    """Service for interacting with Google Cloud Storage."""

    def __init__(self):
        """Initialize GCS client."""
        self.client = None
        try:
            # Try to initialize the client (will work if credentials are available)
            self.client = storage.Client()
        except Exception as e:
            print(f"Warning: Could not initialize GCS client: {e}")
            print("GCS browsing features will be disabled")

    def get_bucket_name(self):
        """Get the bucket name from configuration."""
        gcs_bucket = Config.get_gcs_bucket()
        # Remove gs:// prefix
        return gcs_bucket.replace('gs://', '')

    def list_files(self, prefix='', max_results=100):
        """List files in the GCS bucket.

        Args:
            prefix: Prefix to filter files (e.g., 'media/lc-person-cutouts/')
            max_results: Maximum number of results to return

        Returns:
            List of dictionaries containing file information
        """
        if not self.client:
            return {'success': False, 'error': 'GCS client not initialized', 'files': [], 'directories': []}

        try:
            bucket_name = self.get_bucket_name()
            bucket = self.client.bucket(bucket_name)

            # Use delimiter='/' to get directory-like listing
            iterator = bucket.list_blobs(prefix=prefix, delimiter='/', max_results=max_results)

            # Get the blobs (files in current directory)
            blobs = list(iterator)

            # Get the prefixes (subdirectories)
            prefixes = iterator.prefixes if hasattr(iterator, 'prefixes') else set()

            files = []
            directories = []

            # Process direct files in this directory
            for blob in blobs:
                # Skip directory markers
                if blob.name.endswith('/'):
                    continue

                gcs_path = f"gs://{bucket_name}/{blob.name}"
                media_url = Config.gcs_path_to_media_url(gcs_path)

                files.append({
                    'name': blob.name.split('/')[-1],
                    'path': gcs_path,
                    'size': blob.size,
                    'updated': blob.updated.isoformat() if blob.updated else None,
                    'content_type': blob.content_type,
                    'media_url': media_url,
                    'is_image': blob.content_type and blob.content_type.startswith('image/') if blob.content_type else False
                })

            # Process subdirectories (prefixes)
            for prefix_path in sorted(prefixes):
                # Extract just the directory name (last part before trailing slash)
                dir_name = prefix_path.rstrip('/').split('/')[-1]
                directories.append({
                    'name': dir_name + '/',
                    'full_path': prefix_path,
                    'is_directory': True
                })

            return {
                'success': True,
                'files': files,
                'directories': directories,
                'prefix': prefix,
                'bucket': bucket_name
            }

        except NotFound:
            return {'success': False, 'error': f'Bucket {bucket_name} not found', 'files': [], 'directories': []}
        except Forbidden:
            return {'success': False, 'error': 'Access denied to bucket', 'files': [], 'directories': []}
        except Exception as e:
            return {'success': False, 'error': str(e), 'files': [], 'directories': []}

    def search_images(self, prefix='media/', pattern='', max_results=100):
        """Search for image files in the GCS bucket.

        Args:
            prefix: Prefix to start search from
            pattern: Pattern to match in filename
            max_results: Maximum number of results

        Returns:
            List of image files matching the criteria
        """
        if not self.client:
            return {'success': False, 'error': 'GCS client not initialized', 'files': []}

        try:
            bucket_name = self.get_bucket_name()
            bucket = self.client.bucket(bucket_name)

            blobs = bucket.list_blobs(prefix=prefix, max_results=max_results * 2)  # Get more to filter

            images = []
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff']

            for blob in blobs:
                # Skip directories
                if blob.name.endswith('/'):
                    continue

                # Check if it's an image
                is_image = False
                if blob.content_type and blob.content_type.startswith('image/'):
                    is_image = True
                elif any(blob.name.lower().endswith(ext) for ext in image_extensions):
                    is_image = True

                if not is_image:
                    continue

                # Apply pattern filter if provided
                if pattern and pattern.lower() not in blob.name.lower():
                    continue

                gcs_path = f"gs://{bucket_name}/{blob.name}"
                media_url = Config.gcs_path_to_media_url(gcs_path)

                images.append({
                    'name': blob.name.split('/')[-1],
                    'path': gcs_path,
                    'full_path': blob.name,
                    'size': blob.size,
                    'updated': blob.updated.isoformat() if blob.updated else None,
                    'content_type': blob.content_type,
                    'media_url': media_url
                })

                if len(images) >= max_results:
                    break

            return {
                'success': True,
                'images': images,
                'count': len(images)
            }

        except Exception as e:
            return {'success': False, 'error': str(e), 'images': []}


# Global instance
storage_service = GCSStorageService()
