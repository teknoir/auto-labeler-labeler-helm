"""
Main web application entry point for Vision Dataset Curation.
"""
from flask import Flask, render_template, request, jsonify, Blueprint
from flask_cors import CORS
from database import Database, DatasetRepository, ImageRepository
from config import Config
from storage import storage_service
import os

app = Flask(__name__)
CORS(app)

# Create a Blueprint with the base URL prefix
base_url = Config.get_base_url()
if base_url:
    # Use Blueprint for prefixed routes
    bp = Blueprint('vdc', __name__, url_prefix=base_url)
else:
    # Use Blueprint without prefix for root deployment
    bp = Blueprint('vdc', __name__)

# Initialize database connection
db = Database()

@app.before_request
def before_request():
    """Ensure database connection before each request."""
    if db.client is None:
        db.connect()

# Web Routes
@bp.route('/')
def index():
    """Render the main dataset curation page."""
    return render_template('index.html', base_url=base_url)

# Configuration endpoint
@bp.route('/api/config', methods=['GET'])
def get_config():
    """Get application configuration for frontend."""
    return jsonify({
        'success': True,
        'config': {
            'gcs_bucket': Config.get_gcs_bucket(),
            'media_service_base_url': Config.get_media_service_base_url(),
            'namespace': Config.NAMESPACE,
            'domain': Config.DOMAIN,
            'base_url': base_url
        }
    }), 200

# GCS Storage endpoints
@bp.route('/api/storage/browse', methods=['GET'])
def browse_storage():
    """Browse files in GCS bucket."""
    prefix = request.args.get('prefix', 'media/')
    max_results = int(request.args.get('max_results', 100))

    result = storage_service.list_files(prefix=prefix, max_results=max_results)
    return jsonify(result), 200 if result.get('success') else 500

@bp.route('/api/storage/search', methods=['GET'])
def search_images():
    """Search for images in GCS bucket."""
    prefix = request.args.get('prefix', 'media/')
    pattern = request.args.get('pattern', '')
    max_results = int(request.args.get('max_results', 100))

    result = storage_service.search_images(prefix=prefix, pattern=pattern, max_results=max_results)
    return jsonify(result), 200 if result.get('success') else 500

# API Routes - Datasets
@bp.route('/api/datasets', methods=['GET'])
def get_datasets():
    """Get all datasets."""
    try:
        dataset_repo = DatasetRepository(db)
        datasets = dataset_repo.get_all_datasets()

        # Convert ObjectId to string for JSON serialization
        for dataset in datasets:
            dataset['_id'] = str(dataset['_id'])

        return jsonify({'success': True, 'datasets': datasets}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/datasets', methods=['POST'])
def create_dataset():
    """Create a new dataset."""
    try:
        data = request.get_json()
        dataset_repo = DatasetRepository(db)

        dataset_id = dataset_repo.create_dataset(
            name=data.get('name'),
            description=data.get('description'),
            metadata=data.get('metadata', {})
        )

        return jsonify({
            'success': True,
            'dataset_id': str(dataset_id),
            'message': 'Dataset created successfully'
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/datasets/<dataset_id>', methods=['GET'])
def get_dataset(dataset_id):
    """Get a specific dataset by ID."""
    try:
        dataset_repo = DatasetRepository(db)
        dataset = dataset_repo.get_dataset(dataset_id)

        if dataset:
            dataset['_id'] = str(dataset['_id'])
            return jsonify({'success': True, 'dataset': dataset}), 200
        else:
            return jsonify({'success': False, 'error': 'Dataset not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/datasets/<dataset_id>', methods=['PUT'])
def update_dataset(dataset_id):
    """Update a dataset."""
    try:
        data = request.get_json()
        dataset_repo = DatasetRepository(db)

        updates = {}
        if 'name' in data:
            updates['name'] = data['name']
        if 'description' in data:
            updates['description'] = data['description']
        if 'metadata' in data:
            updates['metadata'] = data['metadata']

        success = dataset_repo.update_dataset(dataset_id, updates)

        if success:
            return jsonify({'success': True, 'message': 'Dataset updated successfully'}), 200
        else:
            return jsonify({'success': False, 'error': 'Dataset not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/datasets/<dataset_id>', methods=['DELETE'])
def delete_dataset(dataset_id):
    """Delete a dataset."""
    try:
        dataset_repo = DatasetRepository(db)
        success = dataset_repo.delete_dataset(dataset_id)

        if success:
            return jsonify({'success': True, 'message': 'Dataset deleted successfully'}), 200
        else:
            return jsonify({'success': False, 'error': 'Dataset not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API Routes - Images
@bp.route('/api/datasets/<dataset_id>/images', methods=['GET'])
def get_images(dataset_id):
    """Get all images for a dataset."""
    try:
        image_repo = ImageRepository(db)
        images = image_repo.get_images_by_dataset(dataset_id)

        # Convert ObjectId to string and add media URLs
        for image in images:
            image['_id'] = str(image['_id'])
            # Convert GCS path to media service URL
            if 'path' in image:
                image['media_url'] = Config.gcs_path_to_media_url(image['path'])

        return jsonify({'success': True, 'images': images}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/datasets/<dataset_id>/images', methods=['POST'])
def create_image(dataset_id):
    """Create a new image entry."""
    try:
        data = request.get_json()
        image_repo = ImageRepository(db)

        # Validate GCS path format
        gcs_path = data.get('path')
        if not gcs_path or not gcs_path.startswith('gs://'):
            return jsonify({
                'success': False,
                'error': 'Invalid GCS path. Must start with gs://'
            }), 400

        image_id = image_repo.create_image(
            dataset_id=dataset_id,
            filename=data.get('filename'),
            path=gcs_path,
            annotations=data.get('annotations', [])
        )

        return jsonify({
            'success': True,
            'image_id': str(image_id),
            'message': 'Image created successfully'
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/images/<image_id>/annotations', methods=['POST'])
def add_annotation(image_id):
    """Add an annotation to an image."""
    try:
        data = request.get_json()
        image_repo = ImageRepository(db)

        success = image_repo.add_annotation(image_id, data)

        if success:
            return jsonify({'success': True, 'message': 'Annotation added successfully'}), 200
        else:
            return jsonify({'success': False, 'error': 'Image not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Health check endpoint
@bp.route('/health')
def health():
    """Health check endpoint."""
    try:
        if db.client is None:
            return jsonify({'status': 'unhealthy', 'message': 'Database not connected'}), 503

        # Ping database
        db.client.admin.command('ping')
        return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'message': str(e)}), 503

# Register the blueprint
app.register_blueprint(bp)

def main():
    """Main application function."""
    print("=" * 60)
    print("Vision Dataset Curation - Web Application")
    print("=" * 60)
    print()

    # Connect to database
    if not db.connect():
        print("Warning: Failed to connect to MongoDB initially. Will retry on first request.")

    # Get port from environment or default to 5000
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')

    print(f"Starting web server on http://{host}:{port}")
    if base_url:
        print(f"Base URL: {base_url}")
    print(f"GCS Bucket: {Config.get_gcs_bucket()}")
    print(f"Media Service: {Config.get_media_service_base_url()}")
    print()

    # Run Flask app
    app.run(host=host, port=port, debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')

if __name__ == "__main__":
    main()
