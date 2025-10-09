"""
Configuration module for the Vision Dataset Curation application.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    NAMESPACE = os.getenv("NAMESPACE", 'demonstrations')
    DOMAIN = os.getenv("DOMAIN", 'teknoir.dev')
    BUCKET_PREFIX = os.getenv("BUCKET_PREFIX", 'media/vision-dataset-curation')
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'vision_dataset_curation')
    MONGO_INITDB_ROOT_USERNAME = os.getenv('MONGO_INITDB_ROOT_USERNAME', 'teknoir')
    MONGO_INITDB_ROOT_PASSWORD = os.getenv('MONGO_INITDB_ROOT_PASSWORD', 'teknoir123456!')

    @classmethod
    def get_mongodb_connection_string(cls):
        """Get the full MongoDB connection string."""
        # If username and password are provided, build authenticated connection string
        if cls.MONGO_INITDB_ROOT_USERNAME and cls.MONGO_INITDB_ROOT_PASSWORD:
            # Parse the URI to inject credentials
            uri = cls.MONGODB_URI
            if uri.startswith('mongodb://'):
                # Remove mongodb:// prefix
                uri_without_prefix = uri[10:]
                # Build authenticated URI
                return f"mongodb://{cls.MONGO_INITDB_ROOT_USERNAME}:{cls.MONGO_INITDB_ROOT_PASSWORD}@{uri_without_prefix}"
            elif uri.startswith('mongodb+srv://'):
                # Remove mongodb+srv:// prefix
                uri_without_prefix = uri[14:]
                # Build authenticated URI
                return f"mongodb+srv://{cls.MONGO_INITDB_ROOT_USERNAME}:{cls.MONGO_INITDB_ROOT_PASSWORD}@{uri_without_prefix}"

        return cls.MONGODB_URI

    @classmethod
    def get_database_name(cls):
        """Get the database name."""
        return cls.MONGODB_DATABASE

    @classmethod
    def get_gcs_bucket(cls):
        """Get the GCS bucket URL."""
        return f"gs://{cls.NAMESPACE}.{cls.DOMAIN}"

    @classmethod
    def get_media_service_base_url(cls):
        """Get the media service base URL."""
        return f"https://{cls.DOMAIN}/{cls.NAMESPACE}/media-service/api/jpeg"

    @classmethod
    def gcs_path_to_media_url(cls, gcs_path):
        """Convert GCS path to media service URL.

        Args:
            gcs_path: Full GCS path like gs://demonstrations.teknoir.dev/media/...

        Returns:
            Media service URL like https://teknoir.dev/demonstrations/media-service/api/jpeg/media/...
        """
        if not gcs_path or not gcs_path.startswith('gs://'):
            return None

        # Remove gs:// prefix
        path_without_prefix = gcs_path[5:]

        # Remove bucket name (namespace.domain)
        bucket_name = f"{cls.NAMESPACE}.{cls.DOMAIN}"
        if path_without_prefix.startswith(bucket_name + '/'):
            # Extract the path after the bucket name
            relative_path = path_without_prefix[len(bucket_name) + 1:]
        else:
            # If path doesn't match expected bucket, try to extract path after first /
            parts = path_without_prefix.split('/', 1)
            relative_path = parts[1] if len(parts) > 1 else path_without_prefix

        # Build media service URL: https://{DOMAIN}/{NAMESPACE}/media-service/api/jpeg/{relative_path}
        return f"https://{cls.DOMAIN}/{cls.NAMESPACE}/media-service/api/jpeg/{relative_path}"
