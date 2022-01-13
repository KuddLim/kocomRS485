from enum import Enum

class DeviceState(Enum):
    MASTER_LIGHT_ON = 'FFFFFFFFFFFFFFFF'
    MASTER_LIGHT_OFF = '0000000000000000'
    SWITCH_ON = 'on'
    SWITCH_OFF = 'off'

class CommandStr(Enum):
    QUERY = '조회'                          # 3a
    STATE = '상태'                          # 00
    ON = 'on'                             # 01
    OFF = 'off'                           # 02
    MASTER_LIGHT_ON = '일괄소등'           # 65
    MASTER_LIGHT_OFF = '일괄소등해제'      # 66

class Room(Enum):
    LIVING_ROOM = 'livingroom'
    BEDROOM = 'bedroom'
    ROOM1 = 'room1'
    ROOM2 = 'room2'
    KITCHEN = 'kitchen'
    MASTER_LIGHT = 'masterlight'

class Device(Enum):
    WALLPAD = 'wallpad'
    LIGHT = 'light'
    THERMOSTAT = 'thermostat'
    PLUG = 'plug'
    GAS = 'gas'
    ELEVATOR = 'elevator'
    FAN = 'fan'

class HAStrings(Enum):
    PREFIX = 'homeassistant'
    SWITCH = 'switch'
    LIGHT = 'light'
    CLIMATE = 'climate'
    SENSOR = 'sensor'
    FAN = 'fan'

class FanSpeed(Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    OFF = 'off'

class DictKey(Enum):
    ADVANCED = 'Advanced'
    INIT_TEMP = 'INIT_TEMP'
    SCAN_INTERVAL = 'SCAN_INTERVAL'
    DEFAULT_SPEED = 'DEFAULT_SPEED'
    LOGLEVEL = 'LOGLEVEL'
    KOCOM_LIGHT_SIZE = 'KOCOM_LIGHT_SIZE'
    KOCOM_PLUG_SIZE = 'KOCOM_PLUG_SIZE'
    KOCOM_ROOM = 'KOCOM_ROOM'
    KOCOM_ROOM_THERMOSTAT = 'KOCOM_ROOM_THERMOSTAT'
    NAME = 'name'
    NUMBER = 'number'

class PacketType(Enum):
    SEND = 'send'
    ACK = 'ack'
    ISSUE = 'issue'

class GrexMode(Enum):
    AUTO = 'auto'
    MANUAL = 'manual'
    SLEEP = 'sleep'
    OFF = 'off'

class GrexSpeed(Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    OFF = 'off'

class ConfigField(Enum):
    FILE = 'rs485.conf'
    LOGFILE = 'rs485.log'
    LOGNAME = 'RS485'
    WALLPAD = 'Wallpad'
    MQTT = 'MQTT'
    DEVICE = 'RS485'
    SERIAL = 'Serial'
    SERIAL_DEVICE = 'SerialDevice'
    SOCKET = 'Socket'
    SOCKET_DEVICE = 'SocketDevice'
    ANONYMOUS = 'anonymous'
    SERVER = 'server'
    USERNAME = 'username'
    PASSWORD = 'password'

class ConfigValue(Enum):
    SERIAL = 'serial'
    SOCKET = 'socket'
    SERVER = 'server'
    PORT = 'port'
    DEVICE = 'device'

class BooleanString(Enum):
    TRUE = 'True'
    FALSE = 'False'

class GeneralString(Enum):
    CONFIG = 'config'
    RS485 = 'rs485'
    BRIDGE = 'bridge'
    LOG_LEVEL = 'log_level'
    RESTART = 'restart'
    REMOVE = 'remove'
    SCAN = 'scan'
    TICK = 'tick'
    STATE = 'state'
    COUNT = 'count'
    SET = 'set'
    LAST = 'last'
    MODE = 'mode'
    SPEED = 'speed'
    CURRENT_TEMP = 'current_temp'
    TARGET_TEMP = 'target_temp'
    PACKET = 'packet'
    CHECKSUM = 'check_sum'
    HEAT = 'heat'
    NAME_HA = 'HA'
    TYPE = 'type'
    KOCOM = 'KOCOM'
    FAN_ONLY = 'fan_only'


class LogLevel(Enum):
    INFO = 'info'
    DEBUG = 'debug'
    WARN = 'warn'