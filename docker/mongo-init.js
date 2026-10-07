// MongoDB Atlas Local Initialization Script for DevMind
db = db.getSiblingDB('devmind');

// Create collections
db.createCollection('users');
db.createCollection('repositories');
db.createCollection('code_chunks');
db.createCollection('analysis_reports');
db.createCollection('query_logs');

// Create standard indexes
db.users.createIndex({ "github_id": 1 }, { unique: true });
db.repositories.createIndex({ "repo_url": 1 });
db.repositories.createIndex({ "owner": 1, "name": 1 }, { unique: true });

db.code_chunks.createIndex({ "repo_id": 1, "file_path": 1 });
db.code_chunks.createIndex({ "chunk_id": 1 }, { unique: true });

print("DevMind MongoDB database and indexes initialized successfully.");
