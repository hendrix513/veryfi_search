import json
import os
import time

from flask import Flask, jsonify, request
from veryfi import Client
from elasticsearch import Elasticsearch

from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import jwt_required
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt

from cryptography.fernet import Fernet

import logging

es = Elasticsearch([os.environ['ELASTICSEARCH_URL']])
es_index = 'documents'


def wait_for_elasticsearch():
    while True:
        try:
            health = es.cluster.health()
            status = health['status']
            if status in ['green', 'yellow']:
                break
        except Exception:
            pass

        time.sleep(5)  # Wait for 5 seconds before checking again


wait_for_elasticsearch()

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

bcrypt = Bcrypt(app)

app.config["JWT_SECRET_KEY"] = os.environ["JWT_SECRET_KEY"]
jwt = JWTManager(app)

key = Fernet.generate_key()
cipher_suite = Fernet(key)

UPLOAD_FOLDER = '/tmp'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.mkdir(UPLOAD_FOLDER)

users = {}


def encrypt_data(data):
    encrypted_data = cipher_suite.encrypt(data.encode())
    return encrypted_data.decode()


def decrypt_data(encrypted_data):
    decrypted_data = cipher_suite.decrypt(encrypted_data.encode())
    return decrypted_data.decode()


def get_client(username):
    user_info = users[username]
    return Client(decrypt_data(user_info['client_id']), decrypt_data(user_info['client_secret']), username,
                  decrypt_data(user_info['api_key']))


def modify_query_with_username(incoming_query):
    # Add the condition for meta.username to the existing query
    modified_query = {
        "query":
            {
                "bool": {
                    "must": [
                        incoming_query["query"],  # The original query
                        {"match": {"meta.owner": {"query": get_jwt_identity()}}}
                    ]
                }
            }}
    return modified_query


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = bcrypt.generate_password_hash(data.get('password'))
    encrypted_data = {
        'client_id': encrypt_data(data.get('client_id')),
        'client_secret': encrypt_data(data.get('client_secret')),
        'api_key': encrypt_data(data.get('api_key')),
        'password': password
    }
    users[username] = encrypted_data
    return jsonify({'message': 'User registered successfully'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if username not in users or not bcrypt.check_password_hash(users[username]['password'], password):
        return jsonify({'message': 'Invalid username or password'}), 401
    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token), 200


@app.route('/doc', methods=['POST'])
@jwt_required()
def upload_doc():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    doc = get_client(get_jwt_identity()).process_document(file_path)

    es.index(index=es_index, body=doc)

    return jsonify({'message': 'Document uploaded successfully', 'doc': doc}), 200


@app.route('/search', methods=['GET'])
@jwt_required()
def search_docs():
    query = json.loads(request.args.get('query'))
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    modified_query = {
        "query":
            {
                "bool": {
                    "must": [
                        query["query"],
                        {"match": {"meta.owner": {"query": get_jwt_identity()}}}
                    ]
                }
            }}

    app.logger.info(f"QUERY: {modified_query}")

    search_results = es.search(index=es_index, body=modified_query)
    hits = search_results['hits']['hits']
    return jsonify({'results': hits}), 200
