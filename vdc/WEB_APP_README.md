# Vision Dataset Curation - Web Application

A Flask-based web application for managing computer vision datasets with a user-friendly interface.

## Features

- 📊 **Dataset Management**: Create, view, update, and delete datasets
- 🖼️ **Image Management**: Add and organize images within datasets
- 🏷️ **Annotation Support**: Add annotations to images
- 💾 **MongoDB Backend**: Persistent storage with MongoDB
- 🔐 **Authentication Support**: MongoDB authentication with username/password
- 🎨 **Modern UI**: Clean, responsive interface with real-time updates
- ✅ **Health Monitoring**: Built-in health check endpoint

## Quick Start

### Local Development

1. **Install dependencies**:
```bash
cd vdc
pip install -r requirements.txt
```

2. **Set environment variables** (optional):
```bash
export MONGODB_URI="mongodb://localhost:27017/"
export MONGODB_DATABASE="vision_dataset_curation"
export MONGO_INITDB_ROOT_USERNAME="your_username"
export MONGO_INITDB_ROOT_PASSWORD="your_password"
export PORT=5000
export HOST="0.0.0.0"
```

3. **Run the application**:
```bash
python main.py
```

4. **Open your browser** and navigate to:
```
http://localhost:5000
```

### Docker Deployment

1. **Build the Docker image**:
```bash
cd vdc
docker build -t vision-dataset-curation:latest .
```

2. **Run with Docker**:
```bash
docker run -p 5000:5000 \
  -e MONGODB_URI="mongodb://host.docker.internal:27017/" \
  -e MONGO_INITDB_ROOT_USERNAME="teknoir" \
  -e MONGO_INITDB_ROOT_PASSWORD="teknoir123456!" \
  vision-dataset-curation:latest
```

### Kubernetes Deployment

Deploy using the Helm chart:
```bash
helm install vdc ./charts/vision-dataset-curation
```

## API Endpoints

### Datasets

- `GET /api/datasets` - Get all datasets
- `POST /api/datasets` - Create a new dataset
- `GET /api/datasets/<id>` - Get a specific dataset
- `PUT /api/datasets/<id>` - Update a dataset
- `DELETE /api/datasets/<id>` - Delete a dataset

### Images

- `GET /api/datasets/<id>/images` - Get all images for a dataset
- `POST /api/datasets/<id>/images` - Add an image to a dataset
- `POST /api/images/<id>/annotations` - Add an annotation to an image

### Health

- `GET /health` - Health check endpoint

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection URI | `mongodb://localhost:27017/` |
| `MONGODB_DATABASE` | Database name | `vision_dataset_curation` |
| `MONGO_INITDB_ROOT_USERNAME` | MongoDB username | None |
| `MONGO_INITDB_ROOT_PASSWORD` | MongoDB password | None |
| `PORT` | Web server port | `5000` |
| `HOST` | Web server host | `0.0.0.0` |
| `FLASK_DEBUG` | Enable debug mode | `False` |

## Project Structure

```
vdc/
├── main.py              # Flask web application
├── config.py            # Configuration management
├── database.py          # Database connection and repositories
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker container definition
├── templates/
│   └── index.html      # Main web interface
└── README.md           # This file
```

## Web Interface

The web application provides two main tabs:

### Datasets Tab
- View all datasets in a grid layout
- Create new datasets with name and description
- Delete existing datasets
- Quick navigation to view dataset images

### Images Tab
- Select a dataset from dropdown
- View all images in the selected dataset
- Add new images with filename and path
- See annotation counts for each image

## Development

### Adding New Features

1. **New API endpoints**: Add routes in `main.py`
2. **Database operations**: Add methods to repository classes in `database.py`
3. **UI updates**: Modify `templates/index.html`

### Testing

Test the health endpoint:
```bash
curl http://localhost:5000/health
```

Test creating a dataset:
```bash
curl -X POST http://localhost:5000/api/datasets \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Dataset", "description": "A test dataset"}'
```

## MongoDB Authentication

The application automatically handles MongoDB authentication when credentials are provided:

- If `MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD` are set, they will be used for authentication
- The connection string is automatically constructed with credentials
- Supports both `mongodb://` and `mongodb+srv://` URI formats

## License

MIT License

