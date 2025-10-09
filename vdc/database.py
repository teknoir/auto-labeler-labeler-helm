"""
Database connection and operations module.
"""
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import Config


class Database:
    """MongoDB database connection manager."""

    def __init__(self):
        """Initialize the database connection."""
        self.client = None
        self.db = None

    def connect(self):
        """Establish connection to MongoDB."""
        try:
            self.client = MongoClient(
                Config.get_mongodb_connection_string(),
                serverSelectionTimeoutMS=5000
            )
            # Test the connection
            self.client.admin.command('ping')
            self.db = self.client[Config.get_database_name()]
            print(f"✓ Connected to MongoDB at {Config.get_mongodb_connection_string()}")
            print(f"✓ Using database: {Config.get_database_name()}")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"✗ Failed to connect to MongoDB: {e}")
            return False

    def disconnect(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            print("✓ Disconnected from MongoDB")

    def get_collection(self, collection_name):
        """Get a collection from the database."""
        if self.db is None:
            raise Exception("Database not connected. Call connect() first.")
        return self.db[collection_name]

    def list_collections(self):
        """List all collections in the database."""
        if self.db is None:
            raise Exception("Database not connected. Call connect() first.")
        return self.db.list_collection_names()


class DatasetRepository:
    """Repository for dataset operations."""

    def __init__(self, database):
        """Initialize the repository with a database connection."""
        self.db = database
        self.collection = self.db.get_collection('datasets')

    def create_dataset(self, name, description, metadata=None):
        """Create a new dataset."""
        dataset = {
            'name': name,
            'description': description,
            'metadata': metadata or {},
            'created_at': None,  # You can add datetime.utcnow() if needed
            'updated_at': None
        }
        result = self.collection.insert_one(dataset)
        print(f"✓ Created dataset with ID: {result.inserted_id}")
        return result.inserted_id

    def get_dataset(self, dataset_id):
        """Get a dataset by ID."""
        from bson.objectid import ObjectId
        return self.collection.find_one({'_id': ObjectId(dataset_id)})

    def get_all_datasets(self):
        """Get all datasets."""
        return list(self.collection.find())

    def update_dataset(self, dataset_id, updates):
        """Update a dataset."""
        from bson.objectid import ObjectId
        result = self.collection.update_one(
            {'_id': ObjectId(dataset_id)},
            {'$set': updates}
        )
        return result.modified_count > 0

    def delete_dataset(self, dataset_id):
        """Delete a dataset."""
        from bson.objectid import ObjectId
        result = self.collection.delete_one({'_id': ObjectId(dataset_id)})
        return result.deleted_count > 0


class ImageRepository:
    """Repository for image operations."""

    def __init__(self, database):
        """Initialize the repository with a database connection."""
        self.db = database
        self.collection = self.db.get_collection('images')

    def create_image(self, dataset_id, filename, path, annotations=None):
        """Create a new image record."""
        image = {
            'dataset_id': dataset_id,
            'filename': filename,
            'path': path,
            'annotations': annotations or [],
            'created_at': None
        }
        result = self.collection.insert_one(image)
        print(f"✓ Created image with ID: {result.inserted_id}")
        return result.inserted_id

    def get_images_by_dataset(self, dataset_id):
        """Get all images for a dataset."""
        return list(self.collection.find({'dataset_id': dataset_id}))

    def add_annotation(self, image_id, annotation):
        """Add an annotation to an image."""
        from bson.objectid import ObjectId
        result = self.collection.update_one(
            {'_id': ObjectId(image_id)},
            {'$push': {'annotations': annotation}}
        )
        return result.modified_count > 0

