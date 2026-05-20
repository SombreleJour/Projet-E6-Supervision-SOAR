from datetime import datetime, timezone
from ..extensions import db


class Sensor(db.Model):
    __tablename__ = 'sensors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sensor_type = db.Column(db.String(50), nullable=False)  # 'DHT22'
    location = db.Column(db.String(100))
    raspberry_id = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)

    readings = db.relationship('SensorReading', back_populates='sensor',
                               lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Sensor {self.name} ({self.sensor_type})>'


class SensorReading(db.Model):
    __tablename__ = 'sensor_readings'

    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id', ondelete='CASCADE'), nullable=False)
    temperature = db.Column(db.Numeric(5, 2))
    humidity = db.Column(db.Numeric(5, 2))
    checksum_ok = db.Column(db.Boolean, default=True)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(timezone.utc))

    sensor = db.relationship('Sensor', back_populates='readings')

    def __repr__(self):
        return f'<SensorReading sensor={self.sensor_id} temp={self.temperature} hum={self.humidity}>'
