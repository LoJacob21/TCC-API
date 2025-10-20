import os 
import json
import threading
import socket
import ssl
import time
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
if uri and uri.startswith("postgresql://"):
    uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
    
app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16*1024*1024
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True
}

db.init_app(app)

# CONFIG SUPABASE
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "imagens")
SUPABASE_DIRECTORY = os.getenv("SUPABASE_DIRECTORY", "fotos")
supabase = None
supabase_initialized = False

def init_supabase():
    global supabase, supabase_initialized
    try:
        print("Supabase - Iniciando conexão...")
        print(f"Supabase - URL: {SUPABASE_URL}")
        print(f"Supabase - Key: {SUPABASE_KEY[:10]}...")
        
        # Configuração mais robusta
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Teste simples de conexão
        print("Supabase - Testando conexão...")
        response = supabase.table('_nonexistent_table').select('*').limit(1).execute()
        
        # Se chegou aqui, a conexão funciona
        print("Supabase - Conexão estabelecida com sucesso!")
        supabase_initialized = True
        return True
        
    except Exception as e:
        print(f"Supabase - Erro na conexão: {str(e)}")
        supabase = None
        supabase_initialized = False
        return False

# CONFIG HIVEMQ - CORRIGIDO
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
TOPICO_LEITURAS = os.getenv("TOPICO_LEITURAS", "greenvision/leituras")

# Forçar IPv4
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
    
    try:
        leituras = LeituraSensor.query \
            .filter(LeituraSensor.data_hora >= limite) \
            .order_by(LeituraSensor.data_hora.desc()) \
            .all()
        return jsonify([l.to_dict() for l in leituras])
    except Exception as e:
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
                "dados": ultima.to_dict(),
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
        imagens = ImagemSensor.query \
            .filter(ImagemSensor.data_hora >= limite) \
            .order_by(ImagemSensor.data_hora.desc()) \
            .all()
            
        lista = [i.to_dict() for i in imagens]
        return jsonify(lista)
    except Exception as e:
        return jsonify({"erro": f"Erro ao buscar imagens: {str(e)}"}), 500

# Rota de upload de imagens
# ROTA DE UPLOAD CORRIGIDA
@app.route('/api/upload', methods=['POST'])
def upload_imagem():
    global supabase, supabase_initialized
    
    if not supabase_initialized or supabase is None:
        print("Supabase - Cliente não inicializado, tentando reconectar...")
        if not init_supabase():
            return jsonify({"erro": "Storage indisponível. Falha na conexão com Supabase"}), 500
    
    try:
        # Verifica se há dados
        if not request.data or len(request.data) == 0:
            return jsonify({"erro": "Nenhum dado de imagem recebido"}), 400
        
        image_data = request.data
        
        # Verificação básica de JPEG
        if len(image_data) < 10 or image_data[0:2] != b'\xff\xd8':
            return jsonify({"erro": "Dados não correspondem a um JPEG válido"}), 400
        
        # Nome do arquivo
        filename = f"{SUPABASE_DIRECTORY}/esp32_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        print(f"Upload - Recebidos {len(image_data)} bytes, salvando como {filename}")
        
        # Upload para Supabase
        try:
            result = supabase.storage.from_(SUPABASE_BUCKET).upload(
                file=image_data,
                path=filename,
                file_options={"content-type": "image/jpeg"}
            )
            
            print(f"Supabase - Upload realizado")
            
        except Exception as upload_error:
            print(f"Supabase - Erro no upload: {str(upload_error)}")
            return jsonify({"erro": f"Falha no upload: {str(upload_error)}"}), 500
        
        # Obtém URL pública
        try:
            public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
            print(f"Supabase - URL pública: {public_url}")
        except Exception as url_error:
            print(f"Supabase - Erro ao obter URL: {url_error}")
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"
        
        # Salva no banco de dados
        try:
            with app.app_context():
                imagem = ImagemSensor(
                    arquivo=public_url, 
                    data_hora=datetime.now(timezone.utc)
                )
                db.session.add(imagem)
                db.session.commit()
            print("DB - Imagem salva no banco com sucesso")
        except Exception as db_error:
            print(f"DB - Erro ao salvar no banco: {db_error}")
            # Não falha o upload por erro no banco
        
        return jsonify({
            "mensagem": "Imagem salva com sucesso",
            "filename": filename,
            "url": public_url,
            "tamanho": len(image_data),
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"Upload - Erro geral: {str(e)}")
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500
    
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
        return jsonify({
            "status": "error",
            "erro": f"Erro ao gerar status: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

# CONFIG MQTT - HiveMQ Cloud
def setup_mqtt_client():
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.reconnect_delay_set(min_delay=1, max_delay=120)
    return client

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"HiveMQ - Conectado ao broker {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(TOPICO_LEITURAS, 1)  # QoS 1
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
                    luminosidade=payload.get("luminosidade"),
                    data_hora=datetime.now(timezone.utc)
                )
                db.session.add(leitura)
                db.session.commit()
                
            print("HiveMQ - Leitura salva no banco de dados")
        
    except Exception as e:
        print(f"HiveMQ - Erro: {str(e)}")

def mqtt_worker():
    print("MQTT - Worker iniciado!")  
    
    while True:
        try:
            print("MQTT - Tentando conectar...")  
            client = setup_mqtt_client()
            client.on_connect = on_connect
            client.on_message = on_message
            
            print(f"MQTT - Conectando ao broker {MQTT_BROKER}:{MQTT_PORT}...")
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            print("MQTT - Conexão estabelecida, iniciando loop...")  
            client.loop_forever()
            
        except Exception as e:
            print(f"MQTT - Erro fatal: {str(e)}")
            print("MQTT - Aguardando 10 segundos antes de reconectar...")  
            time.sleep(10)  
            
# INICIALIZAÇÃO
def create_tables():
    with app.app_context():
        db.create_all()
        print("DB - Tabelas verificadas/criadas")

def start_mqtt():
    print("INICIANDO MQTT...")
    mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True)
    mqtt_thread.start()
    print("MQTT - Thread MQTT iniciada")
    print(f"MQTT - Thread ativa: {mqtt_thread.is_alive()}")
    
def init_supabase_async():
    global supabase
    try:
        print(f"Supabase - Inicializando conexão...")
        supabase_success = init_supabase()
        
        if not supabase_success:
            print("Supabase - Aviso: Conexão falhou. Upload de imagens não funcionará.")
        else:
            print("Supabase - Conexão estabelecida com sucesso!")
    except Exception as e:
        print(f"Supabase - Erro na inicialização: {e}")
        
print("=" * 60)
print("Inicializando API GreenVision...")
print("=" * 60)

# Cria tabelas do banco
try:
    with app.app_context():
        db.create_all()
        print("DB - Tabelas verificadas/criadas")
except Exception as e:
    print(f" DB - Erro ao criar tabelas: {e}")

# Inicia MQTT em thread separada
try:
    print("Iniciando MQTT...")
    mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True)
    mqtt_thread.start()
    print("MQTT - Thread iniciada")
except Exception as e:
    print(f"MQTT - Erro ao iniciar: {e}")

# Inicia Supabase em thread separada  
try:
    print("Iniciando Supabase...")
    supabase_thread = threading.Thread(target=init_supabase_async, daemon=True)
    supabase_thread.start()
except Exception as e:
    print(f"Supabase - Erro ao iniciar: {e}")

print("=" * 60)
print("Render + HiveMQ + Supabase")    
print("=" * 60)

if __name__ == '__main__':
    print("🔧 Modo desenvolvimento local")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True, debug=True)