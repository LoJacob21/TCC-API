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
from sqlalchemy import desc

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
# Configuração Supabase - CORRIGIDA
# ===============================
SUPABASE_URL = "https://" + os.getenv("SUPABASE_URL")  # ADICIONA https://
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "imagens")
SUPABASE_DIRECTORY = os.getenv("SUPABASE_DIRECTORY", "fotos")

# Variável global para o cliente Supabase
supabase = None

def init_supabase():
    """Inicializa o cliente Supabase com tratamento de erro"""
    global supabase
    try:
        print(f"[Supabase] Tentando conectar...")
        print(f"[Supabase] URL: {SUPABASE_URL}")
        print(f"[Supabase] Bucket: {SUPABASE_BUCKET}")
        print(f"[Supabase] Diretório: {SUPABASE_DIRECTORY}")
        
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Testa a conexão listando buckets
        print("[Supabase] Testando conexão...")
        buckets = supabase.storage.list_buckets()
        
        bucket_names = [bucket.name for bucket in buckets]
        print(f"[Supabase] Buckets disponíveis: {bucket_names}")
        
        if SUPABASE_BUCKET not in bucket_names:
            print(f"[Supabase] AVISO: Bucket '{SUPABASE_BUCKET}' não encontrado!")
            return False
            
        print(f"[Supabase] Conectado com sucesso ao bucket: {SUPABASE_BUCKET}")
        return True
        
    except Exception as e:
        print(f"[Supabase] ERRO na conexão: {str(e)}")
        supabase = None
        return False

# ===============================
# Configuração HiveMQ Cloud - CORRIGIDA
# ===============================
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
TOPICO_LEITURAS = os.getenv("TOPICO_LEITURAS", "greenvision/leituras")

# Forçar IPv4 para Render
original_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs):
    responses = original_getaddrinfo(*args, **kwargs)
    ipv4_responses = [x for x in responses if x[0] == socket.AF_INET]
    return ipv4_responses if ipv4_responses else responses

socket.getaddrinfo = getaddrinfo_ipv4

# ===============================
# Rotas Flask (MANTIDAS)
# ===============================
@app.route('/')
def home():
    supabase_status = "conectado" if supabase else "erro"
    return jsonify({
        "mensagem": "API GreenVision funcionando!",
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

@app.route('/leituras/ultima', methods=['GET'])
def ultima_leitura():
    """Retorna apenas a última leitura dos sensores"""
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
    """Upload de imagens direto para o Supabase na pasta 'fotos'"""
    global supabase
    
    # Tenta reconectar se supabase estiver None
    if supabase is None:
        print("[Supabase] Cliente não inicializado, tentando reconectar...")
        if not init_supabase():
            return jsonify({"erro": "Serviço de storage indisponível. Falha na conexão com Supabase."}), 500
        
    try:
        image_data = None
        filename = None
        
        print(f"[Upload] Iniciando upload para Supabase...")
        
        # Verifica se é upload por raw data (da ESP32)
        if request.data:
            image_data = request.data
            if len(image_data) == 0:
                return jsonify({"erro": "Nenhum dado de imagem recebido"}), 400
            
            if len(image_data) < 10 or image_data[0] != 0xFF or image_data[1] != 0xD8:
                return jsonify({"erro": "Dados não correspondem a um JPEG válido"}), 400
            
            # Nome do arquivo com timestamp e na pasta 'fotos'
            filename = f"{SUPABASE_DIRECTORY}/esp32_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            print(f"[Upload] Recebido via raw data: {len(image_data)} bytes")
        else:
            return jsonify({"erro": "Nenhuma imagem recebida. Use raw data"}), 400

        # Faz upload para o Supabase na pasta 'fotos'
        print(f"[Supabase] Fazendo upload de {len(image_data)} bytes como {filename}")
        
        try:
            result = supabase.storage.from_(SUPABASE_BUCKET).upload(
                file=image_data,
                path=filename,
                file_options={"content-type": "image/jpeg"}
            )
            
            print(f"[Supabase] Resultado do upload: {result}")
            
            # Verifica se houve erro
            if hasattr(result, 'error') and result.error:
                error_msg = getattr(result.error, 'message', str(result.error))
                print(f"[Supabase] Erro no upload: {error_msg}")
                return jsonify({"erro": f"Falha no upload para Supabase: {error_msg}"}), 500
                
            print(f"[Supabase] Upload concluído com sucesso")

        except Exception as upload_error:
            print(f"[Supabase] Exceção durante upload: {str(upload_error)}")
            return jsonify({"erro": f"Erro durante upload: {str(upload_error)}"}), 500

        # Obtém URL pública da imagem
        try:
            public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
            print(f"[Supabase] URL pública: {public_url}")
        except Exception as url_error:
            print(f"[Supabase] Erro ao obter URL pública: {url_error}")
            # Constrói URL manualmente
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"
            print(f"[Supabase] URL manual: {public_url}")

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
    global supabase
    
    # Testa conexão com Supabase
    supabase_status = "conectado" if supabase else "erro"
    bucket_status = "indisponível"
    
    if supabase:
        try:
            buckets = supabase.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            bucket_status = "ok" if SUPABASE_BUCKET in bucket_names else "bucket não encontrado"
        except Exception as e:
            bucket_status = f"erro: {str(e)}"
    
    # Busca última leitura
    ultima_leitura = None
    try:
        with app.app_context():
            ultima = LeituraSensor.query.order_by(desc(LeituraSensor.data_hora)).first()
            if ultima:
                ultima_leitura = ultima.data_hora.isoformat()
    except Exception as e:
        ultima_leitura = f"erro: {str(e)}"
    
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
            "leituras_count": LeituraSensor.query.count(),
            "imagens_count": ImagemSensor.query.count(),
            "ultima_leitura": ultima_leitura
        },
        "ambiente": "production"
    })

# ===============================
# Configuração MQTT - HiveMQ Cloud
# ===============================
def setup_mqtt_client():
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    return client

def on_connect(client, userdata, flags, rc):
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
    try:
        if msg.topic == TOPICO_LEITURAS:
            payload = json.loads(msg.payload.decode())
            print(f"[HiveMQ] Dados recebidos: {payload}")
            
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
            
    except Exception as e:
        print(f"[HiveMQ] Erro: {str(e)}")

def mqtt_worker():
    while True:
        try:
            client = setup_mqtt_client()
            client.on_connect = on_connect
            client.on_message = on_message
            
            client.reconnect_delay_set(min_delay=1, max_delay=120)
            
            print(f"[HiveMQ] Conectando ao broker {MQTT_BROKER}:{MQTT_PORT}...")
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_forever()
            
        except Exception as e:
            print(f"[HiveMQ] Erro fatal: {str(e)}")
            threading.Event().wait(10)

# ===============================
# Inicialização
# ===============================
def create_tables():
    with app.app_context():
        db.create_all()
        print("[DB] Tabelas verificadas/criadas")

def start_mqtt():
    mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True)
    mqtt_thread.start()
    print("[HiveMQ] Thread MQTT iniciada")

def init_supabase_async():
    """Inicializa Supabase de forma assíncrona para não bloquear o MQTT"""
    global supabase
    try:
        print(f"[Supabase] Inicializando conexão...")
        supabase_success = init_supabase()
        
        if not supabase_success:
            print("[Supabase] AVISO: Conexão falhou. Upload de imagens não funcionará.")
        else:
            print("[Supabase] Conexão estabelecida com sucesso!")
    except Exception as e:
        print(f"[Supabase] Erro na inicialização: {e}")

if __name__ == '__main__':
    print("=" * 60)
    print("Inicializando API GreenVision...")
    print("=" * 60)
    
    # 1. Primeiro cria as tabelas do banco
    create_tables()
    
    # 2. Inicia MQTT IMEDIATAMENTE (CRÍTICO)
    start_mqtt()
    
    # 3. Inicia Supabase em thread separada para não bloquear
    supabase_thread = threading.Thread(target=init_supabase_async, daemon=True)
    supabase_thread.start()
    
    print("=" * 60)
    print("API GreenVision - HiveMQ + Supabase")
    print("=" * 60)
    print("Configuração:")
    print(f"  Supabase: {SUPABASE_URL}")
    print(f"  Bucket: {SUPABASE_BUCKET}") 
    print(f"  Diretório: {SUPABASE_DIRECTORY}")
    print(f"  MQTT: {MQTT_BROKER}:{MQTT_PORT}")
    print("=" * 60)
    print("Endpoints disponíveis:")
    print(f"  GET  /                 -> Status da API")
    print(f"  GET  /leituras         -> Leituras dos sensores")
    print(f"  GET  /leituras/ultima  -> Última leitura")
    print(f"  GET  /imagens          -> Lista de imagens")
    print(f"  POST /api/upload       -> Upload para Supabase")
    print(f"  GET  /api/status       -> Status do sistema")
    print("=" * 60)

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)