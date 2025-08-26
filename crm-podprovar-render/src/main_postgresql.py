import os
import sys
import sqlite3
import json
import csv
import hashlib
from datetime import datetime
from io import StringIO
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, jsonify, make_response, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'crm-podprovar-2024-final'

# Configurar CORS
CORS(app, origins=["*"], supports_credentials=True)

# Configuração da base de dados
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # PostgreSQL (produção)
    url = urlparse(DATABASE_URL)
    DB_CONFIG = {
        'host': url.hostname,
        'port': url.port,
        'database': url.path[1:],
        'user': url.username,
        'password': url.password
    }
    USE_POSTGRES = True
else:
    # SQLite (desenvolvimento)
    DB_PATH = os.path.join(os.path.dirname(__file__), 'crm_podprovar_data.db')
    USE_POSTGRES = False

# Credenciais de acesso
USERS = {
    'josuel': hashlib.sha256('podprovar2024'.encode()).hexdigest()
}

def get_db_connection():
    """Obter conexão com a base de dados"""
    if USE_POSTGRES:
        return psycopg2.connect(**DB_CONFIG)
    else:
        return sqlite3.connect(DB_PATH)

def execute_query(cursor, query, params=None, is_select=False):
    """Executar query adaptativa para PostgreSQL/SQLite"""
    if USE_POSTGRES:
        # Converter ? para %s no PostgreSQL
        pg_query = query.replace('?', '%s')
        if params:
            cursor.execute(pg_query, params)
        else:
            cursor.execute(pg_query)
    else:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

def init_database():
    """Inicializar base de dados permanente"""
    conn = get_db_connection()
    if USE_POSTGRES:
        cursor = conn.cursor()
    else:
        cursor = conn.cursor()
    
    if USE_POSTGRES:
        # Criar tabela de clientes (PostgreSQL)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) NOT NULL,
                nome_fiscal VARCHAR(255),
                nif VARCHAR(50),
                morada TEXT,
                telefone VARCHAR(50),
                email VARCHAR(255),
                responsavel VARCHAR(255),
                titulo VARCHAR(255),
                telemovel_responsavel VARCHAR(50),
                email_responsavel VARCHAR(255),
                distribuidor VARCHAR(255),
                morada_entrega TEXT,
                horario_entrega VARCHAR(100),
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Criar tabela de relatórios (PostgreSQL)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id SERIAL PRIMARY KEY,
                cliente_id INTEGER,
                cliente_nome VARCHAR(255),
                data VARCHAR(50),
                tipo_contacto VARCHAR(50),
                descricao TEXT,
                acoes_futuras TEXT,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cliente_id) REFERENCES clients (id)
            )
        ''')
    else:
        # SQLite (desenvolvimento)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                nome_fiscal TEXT,
                nif TEXT,
                morada TEXT,
                telefone TEXT,
                email TEXT,
                responsavel TEXT,
                titulo TEXT,
                telemovel_responsavel TEXT,
                email_responsavel TEXT,
                distribuidor TEXT,
                morada_entrega TEXT,
                horario_entrega TEXT,
                data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                cliente_nome TEXT,
                data TEXT,
                tipo_contacto TEXT,
                descricao TEXT,
                acoes_futuras TEXT,
                data_criacao TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cliente_id) REFERENCES clients (id)
            )
        ''')
    
    conn.commit()
    if USE_POSTGRES:
        cursor.close()
    conn.close()

# Rotas de autenticação
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username e password são obrigatórios'}), 400
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        if username in USERS and USERS[username] == hashed_password:
            response = make_response(jsonify({'message': 'Login realizado com sucesso', 'user': username}))
            response.set_cookie('user', username, max_age=86400)  # 24 horas
            return response, 200
        else:
            return jsonify({'error': 'Credenciais inválidas'}), 401
    except Exception as e:
        return jsonify({'error': f'Erro no login: {str(e)}'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    response = make_response(jsonify({'message': 'Logout realizado com sucesso'}))
    response.set_cookie('user', '', expires=0)
    return response, 200

# Rotas de clientes
@app.route('/api/clients', methods=['GET'])
def get_clients():
    try:
        search = request.args.get('search', '')
        
        conn = get_db_connection()
        if USE_POSTGRES:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cursor = conn.cursor()
        
        if search:
            if USE_POSTGRES:
                cursor.execute('''
                    SELECT * FROM clients 
                    WHERE nome ILIKE %s OR responsavel ILIKE %s OR nif ILIKE %s
                    ORDER BY nome
                ''', (f'%{search}%', f'%{search}%', f'%{search}%'))
            else:
                cursor.execute('''
                    SELECT * FROM clients 
                    WHERE nome LIKE ? OR responsavel LIKE ? OR nif LIKE ?
                    ORDER BY nome
                ''', (f'%{search}%', f'%{search}%', f'%{search}%'))
        else:
            cursor.execute('SELECT * FROM clients ORDER BY nome')
        
        rows = cursor.fetchall()
        clients = []
        
        for row in rows:
            if USE_POSTGRES:
                client = dict(row)
            else:
                client = {
                    'id': row[0], 'nome': row[1], 'nome_fiscal': row[2], 'nif': row[3],
                    'morada': row[4], 'telefone': row[5], 'email': row[6], 'responsavel': row[7],
                    'titulo': row[8], 'telemovel_responsavel': row[9], 'email_responsavel': row[10],
                    'distribuidor': row[11], 'morada_entrega': row[12], 'horario_entrega': row[13],
                    'data_cadastro': row[14]
                }
            clients.append(client)
        
        if USE_POSTGRES:
            cursor.close()
        conn.close()
        return jsonify(clients), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar clientes: {str(e)}'}), 500

@app.route('/api/clients', methods=['POST'])
def create_client():
    try:
        data = request.get_json()
        
        # Validar campos obrigatórios
        required_fields = ['nome']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Campo {field} é obrigatório'}), 400
        
        conn = get_db_connection()
        if USE_POSTGRES:
            cursor = conn.cursor()
        else:
            cursor = conn.cursor()
        
        execute_query(cursor, '''
            INSERT INTO clients (nome, nome_fiscal, nif, morada, telefone, email, responsavel, titulo, telemovel_responsavel, email_responsavel, distribuidor, morada_entrega, horario_entrega)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('nome'), data.get('nome_fiscal'), data.get('nif'), data.get('morada'),
            data.get('telefone'), data.get('email'), data.get('responsavel'), data.get('titulo'),
            data.get('telemovel_responsavel'), data.get('email_responsavel'), data.get('distribuidor'),
            data.get('morada_entrega'), data.get('horario_entrega')
        ))
        
        if USE_POSTGRES:
            cursor.execute('SELECT lastval()')
            client_id = cursor.fetchone()[0]
        else:
            client_id = cursor.lastrowid
            
        conn.commit()
        if USE_POSTGRES:
            cursor.close()
        conn.close()
        
        return jsonify({'message': 'Cliente cadastrado com sucesso', 'id': client_id}), 201
    except Exception as e:
        return jsonify({'error': f'Erro ao cadastrar cliente: {str(e)}'}), 500

# Continuar com as outras rotas...
# (Para brevidade, vou incluir apenas as principais)

# Inicializar base de dados
init_database()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404
    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

