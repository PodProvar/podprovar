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

# Configurar base de dados permanente
DB_PATH = os.path.join(os.path.dirname(__file__), 'crm_podprovar_data.db')

# Credenciais de acesso
USERS = {
    'josuel': hashlib.sha256('podprovar2024'.encode()).hexdigest()
}

def init_database():
    """Inicializar base de dados permanente"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Criar tabela de clientes
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
    
    # Criar tabela de relatórios
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
        
        if username in USERS:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash == USERS[username]:
                return jsonify({'message': 'Login realizado com sucesso', 'user': username}), 200
        
        return jsonify({'error': 'Credenciais inválidas'}), 401
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

# Rotas de clientes
@app.route('/api/clients', methods=['GET'])
def get_clients():
    try:
        search = request.args.get('search', '')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if search:
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
            client = {
                'id': row[0], 'nome': row[1], 'nome_fiscal': row[2], 'nif': row[3],
                'morada': row[4], 'telefone': row[5], 'email': row[6], 'responsavel': row[7],
                'titulo': row[8], 'telemovel_responsavel': row[9], 'email_responsavel': row[10],
                'distribuidor': row[11], 'morada_entrega': row[12], 'horario_entrega': row[13],
                'data_cadastro': row[14]
            }
            clients.append(client)
        
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
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO clients (nome, nome_fiscal, nif, morada, telefone, email, responsavel, titulo, telemovel_responsavel, email_responsavel, distribuidor, morada_entrega, horario_entrega)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('nome'), data.get('nome_fiscal'), data.get('nif'), data.get('morada'),
            data.get('telefone'), data.get('email'), data.get('responsavel'), data.get('titulo'),
            data.get('telemovel_responsavel'), data.get('email_responsavel'), data.get('distribuidor'),
            data.get('morada_entrega'), data.get('horario_entrega')
        ))
        
        client_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Cliente cadastrado com sucesso', 'id': client_id}), 201
    except Exception as e:
        return jsonify({'error': f'Erro ao cadastrar cliente: {str(e)}'}), 500

@app.route('/api/clients/<int:client_id>', methods=['DELETE'])
def delete_client(client_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar se cliente existe
        cursor.execute('SELECT id FROM clients WHERE id = ?', (client_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Cliente não encontrado'}), 404
        
        # Deletar relatórios associados
        cursor.execute('DELETE FROM reports WHERE cliente_id = ?', (client_id,))
        
        # Deletar cliente
        cursor.execute('DELETE FROM clients WHERE id = ?', (client_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Cliente excluído com sucesso'}), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao excluir cliente: {str(e)}'}), 500

# Rotas de relatórios
@app.route('/api/reports', methods=['GET'])
def get_reports():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM reports ORDER BY data_criacao DESC')
        rows = cursor.fetchall()
        reports = []
        
        for row in rows:
            report = {
                'id': row[0], 'cliente_id': row[1], 'cliente_nome': row[2], 'data': row[3],
                'tipo_contacto': row[4], 'descricao': row[5], 'acoes_futuras': row[6], 'data_criacao': row[7]
            }
            reports.append(report)
        
        conn.close()
        return jsonify(reports), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar relatórios: {str(e)}'}), 500

@app.route('/api/reports/client/<int:client_id>', methods=['GET'])
def get_reports_by_client(client_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM reports WHERE cliente_id = ? ORDER BY data_criacao DESC LIMIT 10', (client_id,))
        rows = cursor.fetchall()
        reports = []
        
        for row in rows:
            report = {
                'id': row[0], 'cliente_id': row[1], 'cliente_nome': row[2], 'data': row[3],
                'tipo_contacto': row[4], 'descricao': row[5], 'acoes_futuras': row[6], 'data_criacao': row[7]
            }
            reports.append(report)
        
        conn.close()
        return jsonify(reports), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar relatórios do cliente: {str(e)}'}), 500

@app.route('/api/reports', methods=['POST'])
def create_report():
    try:
        data = request.get_json()
        
        # Validar campos obrigatórios
        required_fields = ['cliente_id', 'cliente_nome', 'data', 'tipo_contacto', 'descricao']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Campo {field} é obrigatório'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reports (cliente_id, cliente_nome, data, tipo_contacto, descricao, acoes_futuras)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data.get('cliente_id'), data.get('cliente_nome'), data.get('data'),
            data.get('tipo_contacto'), data.get('descricao'), data.get('acoes_futuras')
        ))
        
        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Relatório criado com sucesso', 'id': report_id}), 201
    except Exception as e:
        return jsonify({'error': f'Erro ao criar relatório: {str(e)}'}), 500

# Rotas de backup
@app.route('/api/backup/status', methods=['GET'])
def backup_status():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM clients')
        total_clients = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM reports')
        total_reports = cursor.fetchone()[0]
        
        conn.close()
        
        # Calcular tamanho do arquivo
        file_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        
        return jsonify({
            'database_path': DB_PATH,
            'total_clients': total_clients,
            'total_reports': total_reports,
            'database_size': size_str,
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao obter status: {str(e)}'}), 500

@app.route('/api/backup/json', methods=['GET'])
def backup_json():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Obter clientes
        cursor.execute('SELECT * FROM clients ORDER BY id')
        client_rows = cursor.fetchall()
        clients = []
        for row in client_rows:
            client = {
                'id': row[0], 'nome': row[1], 'nome_fiscal': row[2], 'nif': row[3],
                'morada': row[4], 'telefone': row[5], 'email': row[6], 'responsavel': row[7],
                'titulo': row[8], 'telemovel_responsavel': row[9], 'email_responsavel': row[10],
                'distribuidor': row[11], 'morada_entrega': row[12], 'horario_entrega': row[13],
                'data_cadastro': row[14]
            }
            clients.append(client)
        
        # Obter relatórios
        cursor.execute('SELECT * FROM reports ORDER BY id DESC')
        report_rows = cursor.fetchall()
        reports = []
        for row in report_rows:
            report = {
                'id': row[0], 'cliente_id': row[1], 'cliente_nome': row[2], 'data': row[3],
                'tipo_contacto': row[4], 'descricao': row[5], 'acoes_futuras': row[6], 'data_criacao': row[7]
            }
            reports.append(report)
        
        conn.close()
        
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'source': 'CRM Pod Provar - Sistema Completo',
            'total_clients': len(clients),
            'total_reports': len(reports),
            'clients': clients,
            'reports': reports
        }
        
        # Criar resposta com arquivo JSON
        json_str = json.dumps(backup_data, ensure_ascii=False, indent=2)
        response = make_response(json_str)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=backup_completo_podprovar_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        return response
    except Exception as e:
        return jsonify({'error': f'Erro ao gerar backup JSON: {str(e)}'}), 500

@app.route('/api/backup/clients-csv', methods=['GET'])
def backup_clients_csv():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM clients ORDER BY id')
        client_rows = cursor.fetchall()
        conn.close()
        
        # Criar CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Cabeçalho
        writer.writerow([
            'ID', 'Nome', 'Nome Fiscal', 'NIF', 'Morada', 'Telefone', 'Email',
            'Responsável', 'Título', 'Telemóvel Responsável', 'Email Responsável',
            'Distribuidor', 'Morada Entrega', 'Horário Entrega', 'Data Cadastro'
        ])
        
        # Dados
        for row in client_rows:
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=clientes_podprovar_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
    except Exception as e:
        return jsonify({'error': f'Erro ao gerar CSV de clientes: {str(e)}'}), 500

@app.route('/api/backup/reports-csv', methods=['GET'])
def backup_reports_csv():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reports ORDER BY id DESC')
        report_rows = cursor.fetchall()
        conn.close()
        
        # Criar CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Cabeçalho
        writer.writerow([
            'ID', 'Cliente ID', 'Cliente Nome', 'Data', 'Tipo Contacto',
            'Descrição', 'Ações Futuras', 'Data Criação'
        ])
        
        # Dados
        for row in report_rows:
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=relatorios_podprovar_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
    except Exception as e:
        return jsonify({'error': f'Erro ao gerar CSV de relatórios: {str(e)}'}), 500

@app.route('/api/backup/database', methods=['GET'])
def backup_database():
    try:
        return send_file(
            DB_PATH,
            as_attachment=True,
            download_name=f'crm_podprovar_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db',
            mimetype='application/octet-stream'
        )
    except Exception as e:
        return jsonify({'error': f'Erro ao descarregar base de dados: {str(e)}'}), 500

# Rota para importar clientes de planilha
@app.route('/api/import/clients', methods=['POST'])
def import_clients():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        # Verificar extensão do arquivo
        if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
            return jsonify({'error': 'Formato não suportado. Use CSV ou Excel'}), 400
        
        # Ler arquivo
        try:
            if file.filename.lower().endswith('.csv'):
                import pandas as pd
                df = pd.read_csv(file)
            else:
                import pandas as pd
                df = pd.read_excel(file)
        except Exception as e:
            return jsonify({'error': f'Erro ao ler arquivo: {str(e)}'}), 400
        
        # Verificar se tem coluna nome
        if 'nome' not in df.columns:
            return jsonify({'error': 'Planilha deve ter coluna "nome"'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        imported_count = 0
        skipped_count = 0
        
        for _, row in df.iterrows():
            nome = str(row.get('nome', '')).strip()
            if not nome or nome.lower() == 'nan':
                skipped_count += 1
                continue
            
            # Verificar se cliente já existe
            cursor.execute('SELECT id FROM clients WHERE nome = ?', (nome,))
            if cursor.fetchone():
                skipped_count += 1
                continue
            
            # Mapear campos da planilha
            nome_fiscal = str(row.get('Nome Comercial', '')).strip() if 'Nome Comercial' in df.columns else ''
            if nome_fiscal.lower() == 'nan':
                nome_fiscal = ''
            
            # Inserir cliente
            cursor.execute('''
                INSERT INTO clients (nome, nome_fiscal, nif, morada, telefone, email, responsavel, titulo, telemovel_responsavel, email_responsavel, distribuidor, morada_entrega, horario_entrega)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                nome, nome_fiscal, '', '', '', '', '', '', '', '', '', '', ''
            ))
            imported_count += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Importação concluída! {imported_count} clientes importados, {skipped_count} ignorados (duplicados ou inválidos)',
            'imported': imported_count,
            'skipped': skipped_count
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro na importação: {str(e)}'}), 500

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
