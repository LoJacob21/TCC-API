import os
import json
import threading
import socket
import ssl
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, abort
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

from models import LeituraSensor, ImagemSensor
from ext import db

# ===============================
# Configuração Flask + Banco
# ===============================

load_dotenv()
app = Flask(__name__)
uri = os.getenv("DATABASE_URI")
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
db.init_app(app)

# ===============================
# Configuração Supabase
# ===============================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "imagens")

# Inicializar cliente Supabase
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(f"[Supabase] Conectado ao bucket: {SUPABASE_BUCKET}")
except Exception as e:
    print(f"[Supabase] Erro na conexão: {e}")
    supabase = None

# ===============================
# Configuração HiveMQ Cloud
# ===============================
MQTT_BROKER = "758972e4960f458cad6ec8df523aea96.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "GreenVision"
MQTT_PASSWORD = "Green@9253"
TOPICO_LEITURAS = "greenvision/leituras"

# Forçar IPv4 para Render
original_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs):
    responses = original_getaddrinfo(*args, **kwargs)
    ipv4_responses = [x for x in responses if x[0] == socket.AF_INET]
    return ipv4_responses if ipv4_responses else responses

socket.getaddrinfo = getaddrinfo_ipv4

# ===============================
# Rotas Flask
# ===============================
@app.route('/')
def home():
    return jsonify({
        "mensagem": "API GreenVision funcionando!",
        "storage": "Supabase",
        "mqtt": "HiveMQ Cloud",
        "endpoints": {
            "leituras": "/leituras?periodo=1d|7d|30d",
            "imagens": "/imagens?periodo=1d|7d|30d",
            "upload": "/api/upload",
            "status": "/api/status"
        }
    })

@app.route('/leituras', methods=['GET'])
def listar_leituras():
    """Retorna leituras dos sensores filtradas por período"""
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
        
    try:
        leituras = LeituraSensor.query \
            .filter(LeituraSensor.data_hora >= limite) \
            .order_by(LeituraSensor.data_hora.desc()) \
            .all()
        return jsonify([l.to_dict() for l in leituras])
    except Exception as e:
        return jsonify({"erro": f"Erro ao buscar leituras: {str(e)}"}), 500

@app.route('/imagens', methods=['GET'])
def listar_imagens():
    """Retorna imagens do Supabase filtradas por período"""
    periodo = request.args.get('periodo', default='1d')
    agora = datetime.now(timezone.utc)

    if periodo == '1d':
        limite = agora - timedelta(days=1)
    elif periodo == '7d':
        limite = agora - timedelta(days=7)
    elif periodo == '30d':
        limite = agora - timedelta(days=30)
    else:
        return jsonify({"erro": "Parâmetro 'periodo' inválido. Use 1d, 7d ou 30d."}), 400

    try:
        imagens = ImagemSensor.query \
            .filter(ImagemSensor.data_hora >= limite) \
            .order_by(ImagemSensor.data_hora.desc()) \
            .all()

        lista = [i.to_dict() for i in imagens]
        return jsonify(lista)
    except Exception as e:
        return jsonify({"erro": f"Erro ao buscar imagens: {str(e)}"}), 500

@app.route('/api/upload', methods=['POST'])
def upload_imagem():
    """Upload de imagens direto para o Supabase"""
    if supabase is None:
        return jsonify({"erro": "Serviço de storage indisponível"}), 500
        
    try:
        image_data = None
        filename = None
        
        print(f"[Upload] Iniciando upload para Supabase...")
        
        # Verifica se é upload por form-data ou raw data
        if 'image' in request.files:
            # Upload via form-data
            file = request.files['image']
            if file.filename == '':
                return jsonify({"erro": "Nenhum arquivo selecionado"}), 400
            
            if not file.filename.lower().endswith(('.jpg', '.jpeg')):
                return jsonify({"erro": "Apenas arquivos JPG/JPEG são permitidos"}), 400
            
            image_data = file.read()
            filename = f"esp32_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            print(f"[Upload] Recebido via form-data: {len(image_data)} bytes")
            
        elif request.data:
            # Upload via raw data (binário direto da ESP32)
            image_data = request.data
            if len(image_data) == 0:
                return jsonify({"erro": "Nenhum dado de imagem recebido"}), 400
            
            # Verifica se é um JPEG válido
            if len(image_data) < 10 or image_data[0] != 0xFF or image_data[1] != 0xD8:
                return jsonify({"erro": "Dados não correspondem a um JPEG válido"}), 400
            
            filename = f"esp32_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            print(f"[Upload] Recebido via raw data: {len(image_data)} bytes")
        else:
            return jsonify({"erro": "Nenhuma imagem recebida. Use form-data com 'image' ou raw data"}), 400

        # Faz upload para o Supabase
        print(f"[Supabase] Fazendo upload de {len(image_data)} bytes como {filename}")
        
        try:
            result = supabase.storage.from_(SUPABASE_BUCKET).upload(
                path=filename,
                file=image_data,
                file_options={
                    "content-type": "image/jpeg",
                    "upsert": False
                }
            )
            
            if hasattr(result, 'error') and result.error:
                error_msg = result.error.message if hasattr(result.error, 'message') else str(result.error)
                print(f"[Supabase] Erro no upload: {error_msg}")
                return jsonify({"erro": f"Falha no upload para Supabase: {error_msg}"}), 500
                
            print(f"[Supabase] Upload concluído com sucesso")

        except Exception as upload_error:
            print(f"[Supabase] Exceção durante upload: {upload_error}")
            return jsonify({"erro": f"Erro durante upload: {str(upload_error)}"}), 500

        # Obtém URL pública da imagem
        try:
            public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
            print(f"[Supabase] URL pública: {public_url}")
        except Exception as url_error:
            print(f"[Supabase] Erro ao obter URL pública: {url_error}")
            return jsonify({"erro": f"Erro ao gerar URL pública: {str(url_error)}"}), 500

        # Salva a URL no banco de dados
        try:
            with app.app_context():
                imagem = ImagemSensor(arquivo=public_url)
                db.session.add(imagem)
                db.session.commit()
            print(f"[DB] URL salva no banco: {public_url}")
        except Exception as db_error:
            print(f"[DB] Erro ao salvar no banco: {db_error}")
            return jsonify({"erro": f"Erro ao salvar no banco: {str(db_error)}"}), 500

        return jsonify({
            "mensagem": "Imagem salva com sucesso no Supabase",
            "filename": filename,
            "url": public_url,
            "tamanho": len(image_data),
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:
        print(f"[Upload] Erro geral: {str(e)}")
        return jsonify({"erro": f"Erro interno no servidor: {str(e)}"}), 500

@app.route('/api/status', methods=['GET'])
def status():
    """Endpoint de status da API"""
    supabase_status = "conectado" if supabase else "erro"
    
    # Testa conexão com Supabase
    bucket_status = "indisponível"
    if supabase:
        try:
            buckets = supabase.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            bucket_status = "ok" if SUPABASE_BUCKET in bucket_names else "bucket não encontrado"
        except:
            bucket_status = "erro"
    
    return jsonify({
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "storage": {
            "supabase": supabase_status,
            "bucket": SUPABASE_BUCKET,
            "status": bucket_status
        },
        "mqtt": {
            "broker": MQTT_BROKER,
            "port": MQTT_PORT,
            "topico": TOPICO_LEITURAS
        },
        "dados": {
            "leituras_count": LeituraSensor.query.count(),
            "imagens_count": ImagemSensor.query.count()
        },
        "ambiente": "production"
    })

# ===============================
# Configuração MQTT - HiveMQ Cloud
# ===============================
def setup_mqtt_client():
    """Configura e retorna cliente MQTT para HiveMQ Cloud"""
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    
    # Configurar TLS/SSL para HiveMQ Cloud
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    return client

def on_connect(client, userdata, flags, rc):
    """Callback quando conecta ao HiveMQ"""
    if rc == 0:
        print(f"[HiveMQ] Conectado com sucesso ao broker {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(TOPICO_LEITURAS)
        print(f"[HiveMQ] Inscrito no tópico: {TOPICO_LEITURAS}")
    else:
        error_codes = {
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorised"
        }
        error_msg = error_codes.get(rc, f"Unknown error code: {rc}")
        print(f"[HiveMQ] Falha na conexão: {error_msg}")

def on_message(client, userdata, msg):
    """Callback quando recebe mensagem MQTT da ESP32"""
    try:
        if msg.topic == TOPICO_LEITURAS:
            payload = json.loads(msg.payload.decode())
            print(f"[HiveMQ] Dados recebidos: {payload}")
            
            # Salva no banco de dados
            with app.app_context():
                leitura = LeituraSensor(
                    temperatura=payload.get("temperatura"),
                    umidade_ar=payload.get("umidade_ar"),
                    umidade_solo=payload.get("umidade_solo"),
                    luminosidade=payload.get("luminosidade")
                )
                db.session.add(leitura)
                db.session.commit()
                
            print("[HiveMQ] Leitura salva no banco de dados")
            
    except json.JSONDecodeError as e:
        print(f"[HiveMQ] Erro: Payload não é JSON válido: {msg.payload}")
    except Exception as e:
        print(f"[HiveMQ] Erro ao processar mensagem: {str(e)}")

def on_disconnect(client, userdata, rc):
    """Callback quando desconecta do HiveMQ"""
    if rc != 0:
        print(f"[HiveMQ] Desconexão inesperada (código: {rc}). Tentando reconectar...")

def mqtt_worker():
    """Thread worker para MQTT - HiveMQ Cloud"""
    while True:
        try:
            client = setup_mqtt_client()
            client.on_connect = on_connect
            client.on_message = on_message
            client.on_disconnect = on_disconnect
            
            # Configurações de reconexão
            client.reconnect_delay_set(min_delay=1, max_delay=120)
            
            print(f"[HiveMQ] Conectando ao broker {MQTT_BROKER}:{MQTT_PORT}...")
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_forever()
            
        except Exception as e:
            print(f"[HiveMQ] Erro fatal na conexão: {str(e)}")
            print("[HiveMQ] Tentando reconectar em 10 segundos...")
            threading.Event().wait(10)

# ===============================
# Inicialização
# ===============================
def create_tables():
    """Cria as tabelas do banco de dados"""
    with app.app_context():
        db.create_all()
        print("[DB] Tabelas verificadas/criadas")

def start_mqtt():
    """Inicia a thread MQTT para HiveMQ"""
    mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True, name="HiveMQ-Thread")
    mqtt_thread.start()
    print("[HiveMQ] Thread MQTT iniciada")

if __name__ == '__main__':
    # Inicialização
    create_tables()
    start_mqtt()
    
    print("=" * 60)
    print("API GreenVision - HiveMQ + Supabase")
    print("=" * 60)
    print("Configuração:")
    print(f"  MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"  MQTT Tópico: {TOPICO_LEITURAS}")
    print(f"  Storage: Supabase ({SUPABASE_BUCKET})")
    print("=" * 60)
    print("Endpoints disponíveis:")
    print(f"  GET  /                 -> Status da API")
    print(f"  GET  /leituras         -> Leituras dos sensores")
    print(f"  GET  /imagens          -> Lista de imagens")
    print(f"  POST /api/upload       -> Upload para Supabase")
    print(f"  GET  /api/status       -> Status do sistema")
    print("=" * 60)

    # Inicia o servidor Flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)