import os
import json
import threading
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, abort, send_from_directory, url_for
from dotenv import load_dotenv
from models import LeituraSensor, ImagemSensor
from ext import db

# Config Flask e BD
load_dotenv()
app = Flask(__name__)
uri = os.getenv('DATABASE_URI')
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGHT'] = 16 *1024 * 1024
db.init_app(app)

# Pasta para salvar imagens
UPLOAD_FOLDER = 'imagens'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Rotas Flask
# Rota inicial da API
@app.route('/')
def home():
    return jsonify({
        'mensagem': 'API está rodando!!',
        'endpoints': {
            'leituras': '/leituras',
            'imagens': '/imagens',
            'upload': '/api/upload', 
            'download': '/uploads/<filename>'
        }
    })

@app.route('/leituras', methods=['GET'])
def listar_leituras():
    # Filtragem de dados de 1d, 7d ou 30d
    periodo = request.args.get('periodo', default='1d')
    agora = datetime.now(timezone.utc)
    
    if periodo == '1d':
        limite = agora - timedelta(days=1)
    elif periodo == '7d':
        limite = agora - timedelta(days=7)
    elif periodo == '30d':
        limite = agora - timedelta(days=30)
    else:
        return abort(400, 'Período inválido, use apenas 1d, 7d ou 30d.')
    
    # Retorna todas as leituras que os sensores fizeram
    try:
        leituras = LeituraSensor.query \
            .filter(LeituraSensor.data_hora >= limite) \
            .order_by(LeituraSensor.data_hora.desc()) \
            .all()
        return jsonify([l.to_dict() for l in leituras])
    except Exception as e:
        return jsonify({'erro': f'Erro ao buscar leituras: {str(e)}'}), 500
    
@app.route('/imagens', methods=['GET'])
def listar_imagens():
    # Retorna imagens salvas filtradas pelo período
    periodo = request.args.get('periodo', default='1d')
    agora = datetime.now(timezone.utc)
    
    if periodo == '1d':
        limite = agora - timedelta(days=1)
    elif periodo == '7d':
        limite = agora - timedelta(days=7)
    elif periodo == '30d':
        limite = agora - timedelta(days=30)
    else:
        return abort(400, 'Período inválido, use apenas 1d, 7d ou 30d.')
    
    try:
        imagens = ImagemSensor.query \
            .filter(ImagemSensor.data_hora >= limite) \
            .order_by(ImagemSensor.data_hora.desc()) \
            .all()
        
        lista = []
        for i in imagens:
            item = i.to_dict()
            item['url'] = url_for('get_imagem', filename=i.arquivo, _external=True)
            lista.append(item)
        
        return jsonify(lista)
    except Exception as e:
        return jsonify({'erro': f'Erro ao buscar imagens: {str(e)}'}), 500

@app.route('/uploads/<filename>', methods=['GET'])
def get_imagem(filename):
    # Serve arquivos de imagem
    try:
        return send_from_directory(UPLOAD_FOLDER, filename)
    except FileNotFoundError:
        return jsonify({'erro': 'Arquivo não encontrado'}), 404
    except Exception as e:
        return jsonify({'erro': f'Erro ao servir imagem: {str(e)}'}), 500
    
@app.route('/api/upload', methods=['POST'])
def upload_imagem():
    # Endpoint para fazer uploads de imagens via HTTP
    try:
        # Verifica se é form-data ou raw-data
        if 'image' in request.files:
            file = request.files['image']   
                     
            if file.filename == '':
                return jsonify({'erro': 'Nenhum arquivo selecionado'}), 400
            
            if not file.filename.lower().endswith(('.jpg', '.jpeg')):
                return jsonify({'erro': 'Apenas arquivos JPG/JPEG são permitidos'}), 400
            
            # Salva o arquivo
            filename = secure_filename(datetime.now().strftime('%Y%m%d_%H%M%S') + '.jpg')
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
        elif request.data:
            # Upload via raw data
            imagem_data = request.data
            if len(imagem_data) == 0:
                return jsonify({'erro': 'Nenhum dado de imagem recebido'}), 400
            
            # Verifica se é um JPEG válido
            if len(imagem_data) > 10 and imagem_data[0] == 0xFF and imagem_data[1] == 0xD8:
                filename = datetime.now().strftime('%Y%m%d_%H%M%S') + '.jpg'
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                
                with open(filepath,  'wb') as f:
                    f.write(imagem_data)
            else:
                return jsonify({'erro': 'Dados não correspondem a um JPEG válido'}), 400
        else:
            return jsonify({'erro': 'Nenhuma imagem recebida.'}), 400
        
        # Salva no banco de dados
        with app.app_context():
            imagem = ImagemSensor(arquivo=filename)
            db.session.add(imagem)
            db.session.commit()
            
        print(f'HTTP - Imagem recebida: {filename}')
        return jsonify({
            'mensagem': 'Imagem salva com sucesso',
            'filename': filename,
            'url': url_for('get_imagem', filename=filename, _external=True),
            'download_url': url_for('get_imagem', filename=filename, _external=True)
        }), 200
        
    except Exception as e:
        print(f'HTTP - Erro no upload: {str(e)}')
        return jsonify({'erro': f'Erro interno no servidor: {str(e)}'}), 500
    
@app.route('/api/status', methods=['GET'])
def status():
    # Para verificar o status da API
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'leituras_count': LeituraSensor.query.count(),
        'imagens_count': ImagemSensor.query.count(),
        'upload_folder': UPLOAD_FOLDER
     })
    
# Configuração do MQTT para os sensores
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
TOPICO_LEITURAS = 'greenvision/leituras'

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f'MQTT - Conectado com sucesso ao broker {MQTT_BROKER}:{MQTT_PORT}')
        client.subscribe(TOPICO_LEITURAS)
        print(f'MQTT - Inscrito no tópico: {TOPICO_LEITURAS}')
    else:
        print(f'MQTT - Falha na conexão. Código: {rc}')
        
def on_message(client, userdata, msg):
    # Retorno quando recebe mensagem MQTT
    try:
        if msg.topic == TOPICO_LEITURAS:
            payload = json.loads(msg.payload.decode())
            print(f'MQTT - Dados recebidos: {payload}')
            
            with app.app_context():
                leitura = LeituraSensor(
                    temperatura=payload.get('temperatura'),
                    umidade_ar=payload.get('umidade_ar'),
                    umidade_solo=payload.get('umidade_solo'),
                    luminosidade=payload.get('luminosidade')
                )
                db.session.add(leitura)
                db.session.commit()
                
            print('MQTT - Leitura salva no banco de dados')
            
    except json.JSONDecodeError:
        print(f'MQTT - Erro: Payload não é JSON válido: {msg.payload}')
    except Exception as e:
        print(f'MQTT - Erro ao processar mensagem: {str(e)}')
        
def on_disconnect(client, userdata, rc):
    # Retorno quando desconecta dp MQTT
    if rc != 0:
        print(f'MQTT - Desconexão inesperada. Tentando reconectar...')
        try:
            client.reconnect()
        except:
            pass

def mqtt_worker():
    # Trabalhador que mantem a conexão ativa
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    # Configurações de reconexão
    client.reconnect_delay_set(min_delay=1, max_delay=120)   
    
    try:
        print(f'MQTT - Conectando ao broker {MQTT_BROKER}:{MQTT_PORT}...')
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f'MQTT - Erro fatal na conexão: {str(e)}')
        print('MQTT - Tentando reconectar em 10 segundos...')
        threading.Event().wait(10)
        mqtt_worker() # Recurso para reconexão
        
# Inicialização
def create_tables():
    # Cria as tabelas do banco de dados
    with app.app_context():
        db.create_all()
        print('DB - Tabelas verificadas/criadas')

def start_mqtt():
    # Inicia a thread MQTT
    mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True, name='MQTT-Thread')
    mqtt_thread.start()
    print('MQTT Thread MQTT iniciada')
    
if __name__ == '__main__':
    create_tables()
    start_mqtt()
    
    print('=' * 60)
    print('API GreenVision Iniciada!')
    print('=' * 60)
    print('Endpoints disponíveis:')
    print(f'    GET /                       -> Status da API')
    print(f'    GET /leituras               -> Listar leituras dos sensores')
    print(f'    GET /imagens                -> Listar imagens')
    print(f'    GET /api/uploads            -> Upload de imagens')
    print(f'    GET /uploads/<file>         -> Download de imagens')
    print(f'    GET /api/status             -> Status do sistema')
    print('=' * 60)
    print('Configuração MQTT:')
    print(f'    Broker: {MQTT_BROKER}:{MQTT_PORT}')
    print(f'    Tópico: {TOPICO_LEITURAS}')
    print('=' * 60)
    
    # Inicia o Flask
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=True)