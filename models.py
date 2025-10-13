from ext import db
from sqlalchemy.sql import func

class LeituraSensor(db.Model):
    __tablename__ = "Leitura_Sensor"
    id = db.Column(db.Integer, primary_key=True)
    temperatura = db.Column(db.Float)
    umidade_ar = db.Column(db.Float)
    umidade_solo = db.Column(db.Float)
    luminosidade = db.Column(db.Float)
    data_hora = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
        return {
            "id": self.id,
            "temperatura": self.temperatura,
            "umidade_ar": self.umidade_ar,
            "umidade_solo": self.umidade_solo,
            "luminosidade": self.luminosidade,
            "data_hora": self.data_hora.strftime("%Y-%m-%d %H:%M:%S") if self.data_hora else None
        }
        
class ImagemSensor(db.Model):
    __tablename__ = "Imagem_Sensor"
    id = db.Column(db.Integer, primary_key=True)
    arquivo = db.Column(db.String, nullable=False)
    data_hora = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
        return {
            "id": self.id,
            "arquivo": self.arquivo,
            "data_hora": self.data_hora.strftime("%Y-%m-%d %H:%M:%S") if self.data_hora else None
        }