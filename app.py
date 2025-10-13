<<<<<<< HEAD
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
=======
import os 
import json
import threading
import socket
import ssl
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, abort
from models import LeituraSensor, ImagemSensor
from supabase import create_client, Client
from dotenv import load_dotenv
from sqlalchemy import desc
from ext import db

# CONFIG FLASK E BANCO
load_dotenv()
app = Flask(__name__)
uri = os.getenv("DATABASE_URI")
app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16*1024*1024
db.init_app(app)

#CONFIG SUPABASE
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "imagens")
SUPABASE_DIRECTORY = os.getenv("SUPABASE_DIRECTORY", "fotos")
supabase = None

def init_supabase():
    global supabase
    try:
        print("Supabase - Tentando conectar...")
        print(f"Supabase - URL: {SUPABASE_URL}")
        print(f"Supabase - Key: {SUPABASE_KEY[:10]}")
        print(f"Supabase - Bucket: {SUPABASE_BUCKET}")
        print(f"Supabase - Diretório: {SUPABASE_DIRECTORY}")
        
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Testa a conexão listando os buckets diaponíveis
        print("Supabase - Testando a conexão...")
        buckets = supabase.storage.list_buckets()
        bucket_names = [bucket.name for bucket in buckets]
        print(f"Supabase - Buckets disponíveis: {bucket_names}") 

        if SUPABASE_BUCKET not in bucket_names:
            print(f"Supabase - Aviso: Bucket '{SUPABASE_BUCKET}' não encontrado!")
            return False
        
        print(f"Supabase - Conectado com sucesso ao bucket: {SUPABASE_BUCKET}")
        return True

    except Exception as e:
        print(f"Supabase - Erro na conexão: {str(e)}")
        supabase = None
        return False

# CONFIG HiveMQ Cloud
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883)) #pq repetir porta ??
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
TOPICO_LEITURAS = os.getenv("TOPICO_LEITURAS", "greenvision/leituras") #pq repetir nome se ta no .env ?

# Forçar o IPv4 para o Render
original_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs):
    responses = original_getaddrinfo(*args, **kwargs)
    ipv4_responses = [x for x in responses if x[0] == socket.AF_INET]
    return ipv4_responses if ipv4_responses else responses

socket.getaddrinfo = getaddrinfo_ipv4

# ROTAS DO FLASK
# Home
@app.route('/')
def home():
    supabase_status = "conectado" if supabase else "erro"
    return jsonify({
        "mensagem": "API está rodando!!",
        "storage": f"Supabase ({supabase_status})",
        "mqtt": "HiveMQ Cloud",
        "endpoints": {
            "leituras": "/leituras?periodo=1d|7d|30d",
            "ultima_leitura": "/leituras/ultima",
            "imagens": "/imagens?periodo=1d|7d|30d",
            "upload": "/api/upload",
            "status": "/api/status"
        }
    })
 
 # Leituras   
@app.route('/leituras', methods=['GET'])
def listar_leituras():
    # Retorna as leituras dos sensores filtradas por período
    periodo = request.args.get("periodo", default="1d")
    agora = datetime.now(timezone.utc)
    
    if periodo == "1d":
        limite = agora - timedelta(days=1)
    elif periodo == "7d":
        limite = agora - timedelta(days=7)
    elif periodo == "30d":
        limite = agora - timedelta(days=30)
    else:
        return jsonify({"erro": "Período inválido! Use 1d, 7d ou 30d."}), 400
    
>>>>>>> 586ff729ec729194941bdd10c6a47c3aff6f6b79
    try:
        leituras = LeituraSensor.query \
            .filter(LeituraSensor.data_hora >= limite) \
            .order_by(LeituraSensor.data_hora.desc()) \
            .all()
        return jsonify([l.to_dict() for l in leituras])
    except Exception as e:
<<<<<<< HEAD
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
=======
        return jsonify({"erro": f"Erro ao buscar leituras: {str(e)}"}), 500

# Pega a última leitura
@app.route('/leituras/ultima', methods=['GET'])
def ultima_leitura():
    # Retorna apenas a última leitura dos sensores
    try:
        ultima = LeituraSensor.query \
            .order_by(desc(LeituraSensor.data_hora)) \
            .first()
        
        if ultima:
            return jsonify({
                "mensagem": "Última leitura encontrada",
                "dados": ultima.to_dict(),
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "mensagem": "Nenhuma leitura encontrada",
                "dados": None
            }), 404 
    
    except Exception as e:
        return jsonify({"erro": f"Erro ao buscar última leitura: {str(e)}"}), 500

# Imagens
@app.route('/imagens', methods=['GET'])
def listar_imagens():
    # Retorna as imagens do supabase com filtro de período
    periodo = request.args.get('periodo', default='1d')
    agora = datetime.now(timezone.utc)
    
    if periodo == "1d":
        limite = agora - timedelta(days=1)
    elif periodo == "7d":
        limite = agora - timedelta(days=7)
    elif periodo == "30d":
        limite = agora - timedelta(days=30)
    else:
        return jsonify({"erro": "Período inválido! Use 1d, 7d ou 30d."}), 400
    
    try: 
>>>>>>> 586ff729ec729194941bdd10c6a47c3aff6f6b79
        imagens = ImagemSensor.query \
            .filter(ImagemSensor.data_hora >= limite) \
            .order_by(ImagemSensor.data_hora.desc()) \
            .all()
<<<<<<< HEAD
        
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
=======
            
        lista = [i.to_dict() for i in imagens]
        return jsonify(lista)
    except Exception as e:
        return jsonify({"erro": f"Erro ao buscar imagens: {str(e)}"}), 500

# Rota de upload de imagens
@app.route('/api/upload', methods=['POST'])
def upload_imagem():
    global supabase
    
    if supabase is None:
        print("Supabase - Cliente não inicializado, tentando reconectar...")
        if not init_supabase():
            return jsonify({"erro": "Storage indisponível. Falha na conexão com Supabase"}), 500
    
    try:
        image_data = None
        filename = None
        print("Upload - Iniciando upload para o Supabase...")
        
        if request.data:
            image_data = request.data
            if len(image_data) == 0:
                return jsonify({"erro": "Nenhum dado de imagem recebido"}), 400
            
            if len(image_data) < 10 or image_data[0] != 0xFF or image_data[1] != 0xD8:
                return jsonify({"erro": "Dados não correspondem a um JPEG válido"}), 400
            
            filename = f"{SUPABASE_DIRECTORY}/esp32_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            print(f"Upload - Recebido via raw data: {len(image_data)} bytes")
        else:
            return jsonify({"erro": "Nenhuma imagem recebida. Use raw data"}), 400
        
        # Faz upload para o Supabase
        print(f"Supabase - Fazendo upload de {len(image_data)} bytes como {filename}")
        
        try:
            result = supabase.storage.from_(SUPABASE_BUCKET).upload(
                file=image_data,
                path=filename,
                file_options={"content-type": "image/jpeg"}
            )    
            
            print(f"Supabase - Resultado do upload: {result}")
            
            if hasattr(result, 'error') and result.error:
                error_msg = getattr(result.error, 'message', str(result.error))
                print(f"Supabase - Erro no upload: {error_msg}")
                return jsonify({"erro": f"Falha no upload para o Supabase: {error_msg}"}), 500
            
            print(f"Supabase - Upload concluído com sucesso")
        
        except Exception as upload_error:
            print(f"Supabase - Exceção durante upload: {str(upload_error)}")
            return jsonify({"erro": f"Erro durante upload: {str(upload_error)}"}), 500
        
        # Obtém URL pública da imagem
        try:
            public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
            print(f"Supabase - URL pública: {public_url}")
        except Exception as url_error:
            print(f"Supabase - Erro ao obter URL pública: {url_error}")
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"
            print(f"Supabase - URL manual: {public_url}")
        
        # ⭐⭐ CORREÇÃO: Este bloco deve estar DENTRO do try principal
        # Salva a url no banco de dados
        try:
            with app.app_context():
                imagem = ImagemSensor(arquivo=public_url, data_hora=datetime.now(timezone.utc))
                db.session.add(imagem)
                db.session.commit()
            print(f"DB - URL salva no banco: {public_url}")
        except Exception as db_error:
            print(f"DB - Erro ao salvar no banco: {db_error}")
            return jsonify({"erro": f"Erro ao salvar no banco: {str(db_error)}"}), 500
        
        # ⭐⭐ CORREÇÃO: Return deve estar aqui, não fora do try
        return jsonify({
            "mensagem": "Imagem foi salva no Supabase",
            "filename": filename,
            "url": public_url,
            "tamanho": len(image_data),
            "timestamp": datetime.now().isoformat()
        }), 200
            
    except Exception as e:
        print(f"Upload - Erro geral: {str(e)}")
        return jsonify({"erro": f"Erro interno no servidor: {str(e)}"}), 500
    
# Rota do status da api       
@app.route('/api/status', methods=['GET'])
def status():
    global supabase
    
    try:
        # Testa a conexão com supabase
        supabase_status = "conectado" if supabase else "erro"
        bucket_status = "indisponível"
        
        if supabase:
            try:
                buckets = supabase.storage.list_buckets()
                bucket_names = [b.name for b in buckets]
                bucket_status = "ok" if SUPABASE_BUCKET in bucket_names else "bucket não encontrado"
            except Exception as e:
                bucket_status = f"erro: {str(e)}"
        
        # Buscar a última leitura
        ultima_leitura = None
        leituras_count = 0
        imagens_count = 0
        
        try:
            with app.app_context():
                ultima = LeituraSensor.query.order_by(desc(LeituraSensor.data_hora)).first()
                if ultima:
                    ultima_leitura = ultima.data_hora.isoformat()
                
                leituras_count = LeituraSensor.query.count()
                imagens_count = ImagemSensor.query.count()
                
        except Exception as e:
            ultima_leitura = f"erro: {str(e)}"
        
        # ⭐⭐ CORREÇÃO: Return garantido com try/except
        return jsonify({
            "status": "online",
            "timestamp": datetime.now().isoformat(),
            "storage": {
                "supabase": supabase_status,
                "bucket": SUPABASE_BUCKET,
                "diretorio": SUPABASE_DIRECTORY,
                "status": bucket_status,
                "url": SUPABASE_URL
            },
            "mqtt": {
                "broker": MQTT_BROKER,
                "port": MQTT_PORT,
                "topico": TOPICO_LEITURAS
            },
            "dados": {
                "leituras_count": leituras_count,
                "imagens_count": imagens_count,
                "ultima_leitura": ultima_leitura
            },
            "ambiente": "production"
        })
        
    except Exception as e:
        # ⭐⭐ CORREÇÃO: Fallback se tudo der errado
        return jsonify({
            "status": "error",
            "erro": f"Erro ao gerar status: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

# CONFIG MQTT - HiveMQ Cloud
#CONFIG DO CLIENTE
def setup_mqtt_client():
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.reconnect_delay_set(min_delay=1, max_delay=120) #QoS e reconexão para quando o render "dormir"
    return client

#CONFIG DA CONEXÃO
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"HiveMQ - Conectado ao broker {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(TOPICO_LEITURAS, 1) #QoS 1
        print(f"HiveMQ - Inscrito no tópico: {TOPICO_LEITURAS}")
    else:
        error_codes = {
            1: "Conexão recusada - versão do protocolo incorreta",
            2: "Conexão recusada - identificador de cliente inválido",
            3: "Conexão recusada - servidor indisponível",
            4: "Conexão recusada - nome de usuário ou senha incorretos",
            5: "Conexão recusada - não autorizada"
        }
        error_msg = error_codes.get(rc, f"Código de erro desconhecido: {rc}")
        print(f"HiveMQ - Falha na conexão: {error_msg}")

#CONFIG DAS MENSAGENS
def on_message(client, userdata, msg):
    try:
        if msg.topic == TOPICO_LEITURAS:
            payload = json.loads(msg.payload.decode())
            print(f"HiveMQ - Dados recebidos: {payload}")
            
            with app.app_context():
                leitura = LeituraSensor(
                    temperatura=payload.get("temperatura"),
                    umidade_ar=payload.get("umidade_ar"),
                    umidade_solo=payload.get("umidade_solo"),
                    luminosidade=payload.get("luminosidade")
>>>>>>> 586ff729ec729194941bdd10c6a47c3aff6f6b79
                )
                db.session.add(leitura)
                db.session.commit()
                
<<<<<<< HEAD
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
    
=======
            print("HiveMQ - Leitura salva no banco de dados")
        
    except Exception as e:
        print(f"HiveMQ - Erro: {str(e)}")

def mqtt_worker():
    while True:
        try:
            client = setup_mqtt_client()
            client.on_connect = on_connect
            client.on_message = on_message
            
            print(f"HiveMQ - Conectando ao broker {MQTT_BROKER}:{MQTT_PORT}...")
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_forever()
            
        except Exception as e:
            print(f"HiveMQ - Erro fatal: {str(e)}")
            threading.Event().wait(10)
            
# INICIALIZAÇÃO
# Cria tabela do bd caso não tenha
def create_tables():
    with app.app_context():
        db.create_all()
        print("DB - Tabelas verificadas/criadas")

# Inicia o MQTT
def start_mqtt():
    mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True)
    mqtt_thread.start()
    print("HiveMQ - Thread MQTT iniciada")
    
# Inicia o Supabase    
def init_supabase_async():
    global supabase
    try:
        print(f"Supabase - Inicializando conexão...")
        supabase_sucess = init_supabase()
        
        if not supabase_sucess:
            print("Supabase - Conexão estabelecida com sucesso!")
    except Exception as e:
        print(f"Supabase - Erro na inicialização: {e}")
        
if __name__ == '__main__':
    print("=" * 60)
    print("Inicializando API...")
    print("=" * 60)
    
    create_tables()
    start_mqtt()
    supabase_thread = threading.Thread(target=init_supabase_async, daemon=True)
    supabase_thread.start()
    
print("=" * 60)
print("Render + HiveMQ + Supabase")    
print("=" * 60)
print("Configuração:")
print(f"  Supabase: {SUPABASE_URL}")
print(f"  Bucket: {SUPABASE_BUCKET}")
print(f"  Diretório: {SUPABASE_DIRECTORY}")
print(f"  MQTT: {MQTT_BROKER}:{MQTT_PORT}")
print("=" * 60)
print("Endpoints disponíveis:")
print(f"  GET  /                -> Statu da API ")
print(f"  GET  /leituras        -> Leituras dos sensores")
print(f"  GET  /leituras/ultima -> última leitura")
print(f"  GET  /imagens         -> Lista de imagens")
print(f"  POST /api/upload      -> Upload para Supabase")
print(f"  GET  /api/status      -> Status do sistemas")
print(f"=" * 60)

port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port, threaded=True)
>>>>>>> 586ff729ec729194941bdd10c6a47c3aff6f6b79
