# config.py - CanSat Final Pin Configuration

# --- 1. Motor Driver (TB6612FNG) ---
# Left Motor
MOTOR_L_PWM = 18  # Pin 12 (GPIO 18)
MOTOR_L_IN1 = 27  # Pin 13 (GPIO 27)
MOTOR_L_IN2 = 17  # Pin 11 (GPIO 17)

# Right Motor
MOTOR_R_PWM = 13  # Pin 33 (GPIO 13)
MOTOR_R_IN1 = 22  # Pin 15 (GPIO 22)
MOTOR_R_IN2 = 24  # Pin 18 (GPIO 24) ★ここを変更しました

# --- 2. Parachute Mechanism (MOSFET) ---
PARA_TRIGGER_PIN = 4  # Pin 7 (GPIO 4)
PARA_BURN_TIME = 5.0  # Seconds

# --- 3. ToF Sensors (VL53L1X) ---
# I2C Pins: SDA=2 (Pin 3), SCL=3 (Pin 5)
TOF_FRONT_XSHUT = 19  # Pin 35 (GPIO 19) ★ここを変更しました
TOF_REAR_XSHUT  = 26  # Pin 37 (GPIO 26) ★ここを変更しました
TOF_FRONT_ADDR  = 0x30
TOF_REAR_ADDR   = 0x29

# --- 4. Pressure Sensor (DPS310) ---
# SPI Pins: SCLK=11 (Pin 23), MISO=9 (Pin 21), MOSI=10 (Pin 19)
PRESSURE_CS_PIN = 8   # Pin 24 (GPIO 8/CE0)

# --- 5. GPS Module ---
# UART Pins: TX=14 (Pin 8), RX=15 (Pin 10)
GPS_BAUDRATE = 9600

# --- 6. IMU (BNO055) ---
# I2C Pins: SDA=2 (Pin 3), SCL=3 (Pin 5)
IMU_ADDR = 0x28