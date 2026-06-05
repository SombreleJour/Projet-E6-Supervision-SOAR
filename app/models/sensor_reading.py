from datetime import datetime, timezone
from ..extensions import db


# Table des capteurs physiques (ici le DHT22 sur le Raspberry Pi 5)
class Sensor(db.Model):
    __tablename__ = 'sensors'

    id = db.Column(db.Integer, primary_key=True)            # identifiant unique
    name = db.Column(db.String(100), nullable=False)        # nom du capteur
    sensor_type = db.Column(db.String(50), nullable=False)  # type de capteur : 'DHT22'
    location = db.Column(db.String(100))                    # emplacement physique
    raspberry_id = db.Column(db.String(100))               # identifiant du Raspberry qui l'heberge
    is_active = db.Column(db.Boolean, default=True)        # capteur actif ou non

    # Un capteur produit plusieurs releves (supprimes en cascade avec le capteur)
    readings = db.relationship('SensorReading', back_populates='sensor',
                               lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Sensor {self.name} ({self.sensor_type})>'


# Table des releves : chaque mesure de temperature / humidite envoyee par le capteur
class SensorReading(db.Model):
    __tablename__ = 'sensor_readings'

    id = db.Column(db.Integer, primary_key=True)            # identifiant unique
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id', ondelete='CASCADE'), nullable=False)
    temperature = db.Column(db.Numeric(5, 2))              # temperature en degres C (2 decimales)
    humidity = db.Column(db.Numeric(5, 2))                 # humidite en %
    checksum_ok = db.Column(db.Boolean, default=True)     # True si la mesure du capteur est valide
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(timezone.utc))  # horodatage du releve

    # Lien vers le capteur d'origine
    sensor = db.relationship('Sensor', back_populates='readings')

    def __repr__(self):
        return f'<SensorReading sensor={self.sensor_id} temp={self.temperature} hum={self.humidity}>'
