# -*- coding: utf-8 -*-
'''
python -m pip install pyserial
python -m pip install paho-mqtt
'''
import os
import os.path
import serial
import socket
import time
import platform
import threading
import json
import logging
import logging.config
import logging.handlers
import configparser
import paho.mqtt.client as mqtt
from collections import OrderedDict
from kocomEnum import *

# Version
SW_VERSION = 'RS485 Compilation 1.0.3b'
# Log Level
CONF_LOGLEVEL = 'info' # debug, info, warn

###############################################################################################################
################################################## K O C O M ##################################################
# 본인에 맞게 수정하세요


# 보일러 초기값
INIT_TEMP = 22
# 환풍기 초기속도 ['low', 'medium', 'high']
DEFAULT_SPEED = FanSpeed.MEDIUM

# 조명 / 플러그 갯수
KOCOM_LIGHT_SIZE            = {Room.LIVING_ROOM: 3, Room.BEDROOM: 2, Room.ROOM1: 2, Room.ROOM2: 2, Room.KITCHEN: 3, Room.MASTER_LIGHT: 1}
KOCOM_PLUG_SIZE             = {Room.LIVING_ROOM: 2, Room.BEDROOM: 2, Room.ROOM1: 2, Room.ROOM2: 2, Room.KITCHEN: 2}

# 방 패킷에 따른 방이름 (패킷1: 방이름1, 패킷2: 방이름2 . . .)
# 월패드에서 장치를 작동하며 방이름(livingroom, bedroom, room1, room2, kitchen 등)을 확인하여 본인의 상황에 맞게 바꾸세요
# 조명/콘센트와 난방의 방패킷이 달라서 두개로 나뉘어있습니다.
KOCOM_ROOM                  = {'00': Room.LIVING_ROOM, '01': Room.BEDROOM, '02': Room.ROOM2, '03': Room.ROOM1, '04': Room.KITCHEN, 'ff': Room.MASTER_LIGHT}
KOCOM_ROOM_THERMOSTAT       = {'00': Room.LIVING_ROOM, '01': Room.BEDROOM, '02': Room.ROOM1, '03': Room.ROOM2}

# TIME 변수(초)
SCAN_INTERVAL = 300         # 월패드의 상태값 조회 간격
SCANNING_INTERVAL = 0.8     # 상태값 조회 시 패킷전송 간격
####################### Start Here by Zooil ###########################
option_file = '/data/options.json'
if os.path.isfile(option_file):
    with open(option_file) as json_file:
        json_data = json.load(json_file)
        INIT_TEMP = json_data[DictKey.ADVANCED][DictKey.INIT_TEMP]
        SCAN_INTERVAL = json_data[DictKey.ADVANCED][DictKey.SCAN_INTERVAL]
        SCANNING_INTERVAL = json_data[DictKey.ADVANCED][DictKey.SCANNING_INTERVAL]
        DEFAULT_SPEED = json_data[DictKey.ADVANCED][DictKey.DEFAULT_SPEED]
        CONF_LOGLEVEL = json_data[DictKey.ADVANCED][DictKey.LOGLEVEL]
        KOCOM_LIGHT_SIZE = {}
        dict_data = json_data[DictKey.KOCOM_LIGHT_SIZE]
        for i in dict_data:
            KOCOM_LIGHT_SIZE[i[DictKey.NAME]] = i[DictKey.NUMBER]
        KOCOM_PLUG_SIZE = {}
        dict_data = json_data[DictKey.KOCOM_PLUG_SIZE]
        for i in dict_data:
            KOCOM_PLUG_SIZE[i[DictKey.NAME]] = i[DictKey.NUMBER]
        num = 0
        KOCOM_ROOM = {}
        list_data = json_data[DictKey.KOCOM_ROOM]
        for i in list_data:
            if num < 10:
                num_key = "0%d" % (num)
            else:
                num_key = "%d" % (num)
            KOCOM_ROOM[num_key] = i
            num += 1
        num = 0
        KOCOM_ROOM_THERMOSTAT = {}
        list_data = json_data[DictKey.KOCOM_ROOM_THERMOSTAT]
        for i in list_data:
            if num < 10:
                num_key = "0%d" % (num)
            else:
                num_key = "%d" % (num)
            KOCOM_ROOM_THERMOSTAT[num_key] = i
            num += 1
####################### End Here by Zooil ###########################
###############################################################################################################

###############################################################################################################
################################################# 수 정 금 지 ##################################################
################################################# 수 정 금 지 ##################################################
################################################# 수 정 금 지 ##################################################
###############################################################################################################


# KOCOM 코콤 패킷 기본정보
KOCOM_DEVICE                = {'01': Device.WALLPAD, '0e': Device.LIGHT, '36': Device.THERMOSTAT, '3b': Device.PLUG,'44': Device.ELEVATOR, '2c': Device.GAS, '48': Device.FAN}
KOCOM_COMMAND               = {'3a': CommandStr.QUERY, '00': CommandStr.STATE, '01': CommandStr.ON, '02': CommandStr.OFF, '65': CommandStr.MASTER_LIGHT_ON, '66': CommandStr.MASTER_LIGHT_OFF}
KOCOM_TYPE                  = {'30b': PacketType.SEND, '30d': PacketType.ACK, '309': PacketType.ISSUE}
KOCOM_FAN_SPEED             = {'4': FanSpeed.LOW, '8': FanSpeed.MEDIUM, 'c': FanSpeed.HIGH, '0': FanSpeed.OFF}
KOCOM_DEVICE_REV            = {v: k for k, v in KOCOM_DEVICE.items()}
KOCOM_ROOM_REV              = {v: k for k, v in KOCOM_ROOM.items()}
KOCOM_ROOM_THERMOSTAT_REV   = {v: k for k, v in KOCOM_ROOM_THERMOSTAT.items()}
KOCOM_COMMAND_REV           = {v: k for k, v in KOCOM_COMMAND.items()}
KOCOM_TYPE_REV              = {v: k for k, v in KOCOM_TYPE.items()}
KOCOM_FAN_SPEED_REV         = {v: k for k, v in KOCOM_FAN_SPEED.items()}
KOCOM_ROOM_REV[Device.WALLPAD] = '00'

# KOCOM TIME 변수
KOCOM_INTERVAL = 100
VENTILATOR_INTERVAL = 150

# GREX 그렉스 전열교환기 패킷 기본정보
GREX_MODE                   = {'0100': GrexMode.AUTO, '0200': GrexMode.MANUAL, '0300': GrexMode.SLEEP, '0000': GrexMode.OFF}
GREX_SPEED                  = {'0101': GrexSpeed.LOW, '0202': GrexSpeed.MEDIUM, '0303': GrexSpeed.HIGH, '0000': GrexSpeed.OFF}

# CONFIG 파일 변수값

# Log 폴더 생성 (도커 실행 시 로그폴더 매핑)
def make_folder(folder_name):
    if not os.path.isdir(folder_name):
        os.mkdir(folder_name)
root_dir = str(os.path.dirname(os.path.realpath(__file__)))
log_dir = root_dir + '/log/'
make_folder(log_dir)
conf_path = str(root_dir + '/'+ ConfigField.FILE)
log_path = str(log_dir + '/' + ConfigField.LOGFILE)

class rs485:
    def __init__(self):
        self._mqtt_config = {}
        self._port_url = {}
        self._device_list = {}
        self._wp_list = {}
        self.type = None

        config = configparser.ConfigParser()
        config.read(conf_path)

        get_conf_wallpad = config.items(ConfigField.WALLPAD)
        for item in get_conf_wallpad:
            self._wp_list.setdefault(item[0], item[1])
            logger.info('[CONFIG] {} {} : {}'.format(ConfigField.WALLPAD, item[0], item[1]))

        get_conf_mqtt = config.items(ConfigField.MQTT)
        for item in get_conf_mqtt:
            self._mqtt_config.setdefault(item[0], item[1])
            logger.info('[CONFIG] {} {} : {}'.format(ConfigField.MQTT, item[0], item[1]))

        d_type = config.get(ConfigField.LOGNAME, GeneralString.TYPE).lower()
        if d_type == 'serial':
            self.type = d_type
            get_conf_serial = config.items(ConfigField.SERIAL)
            port_i = 1
            for item in get_conf_serial:
                if item[1] != '':
                    self._port_url.setdefault(port_i, item[1])
                    logger.info('[CONFIG] {} {} : {}'.format(ConfigField.SERIAL, item[0], item[1]))
                port_i += 1

            get_conf_serial_device = config.items(ConfigField.SERIAL_DEVICE)
            port_i = 1
            for item in get_conf_serial_device:
                if item[1] != '':
                    self._device_list.setdefault(port_i, item[1])
                    logger.info('[CONFIG] {} {} : {}'.format(ConfigField.SERIAL_DEVICE, item[0], item[1]))
                port_i += 1
            self._con = self.connect_serial(self._port_url)
        elif d_type == 'socket':
            self.type = d_type
            server = config.get(ConfigField.SOCKET, ConfigValue.SERVER)
            port = config.get(ConfigField.SOCKET, ConfigValue.PORT)
            self._socket_device = config.get(ConfigField.SOCKET_DEVICE, ConfigValue.DEVICE)
            self._con = self.connect_socket(server, port)
        else:
            logger.info('[CONFIG] SERIAL / SOCKET IS NOT VALID')
            logger.info('[CONFIG] EXIT RS485')
            exit(1)

    @property
    def _wp_light(self):
        return True if self._wp_list[Device.LIGHT] == BooleanString.TRUE else False

    @property
    def _wp_fan(self):
        return True if self._wp_list[Device.FAN] == BooleanString.TRUE else False

    @property
    def _wp_thermostat(self):
        return True if self._wp_list[Device.THERMOSTAT] == BooleanString.TRUE else False

    @property
    def _wp_plug(self):
        return True if self._wp_list[Device.PLUG] == BooleanString.TRUE else False

    @property
    def _wp_gas(self):
        return True if self._wp_list[Device.GAS] == BooleanString.TRUE else False

    @property
    def _wp_elevator(self):
        return True if self._wp_list[Device.ELEVATOR] == BooleanString.TRUE else False

    @property
    def _device(self):
        if self.type == ConfigValue.SERIAL:
            return self._device_list
        elif self.type == ConfigValue.SOCKET:
            return self._socket_device

    @property
    def _type(self):
        return self.type

    @property
    def _connect(self):
        return self._con

    @property
    def _mqtt(self):
        return self._mqtt_config

    def connect_serial(self, port):
        ser = {}
        opened = 0
        for p in port:
            try:
                ser[p] = serial.Serial(port[p], 9600, timeout=None)
                if ser[p].isOpen():
                    ser[p].bytesize = 8
                    ser[p].stopbits = 1
                    ser[p].autoOpen = False
                    logger.info('Port {} : {}'.format(p, port[p]))
                    opened += 1
                else:
                    logger.info('시리얼포트가 열려있지 않습니다.[{}]'.format(port[p]))
            except serial.serialutil.SerialException:
                logger.info('시리얼포트에 연결할 수 없습니다.[{}]'.format(port[p]))
        if opened == 0: return False
        return ser

    def connect_socket(self, server, port):
        soc = socket.socket()
        soc.settimeout(10)
        try:
            soc.connect((server, int(port)))
        except Exception as e:
            logger.info('소켓에 연결할 수 없습니다.[{}][{}:{}]'.format(e, server, port))
            return False
        soc.settimeout(None)
        return soc

class Kocom(rs485):
    def __init__(self, client, name, device, packet_len):
        self.client = client
        self._name = name
        self.connected = True

        self.ha_registry = False
        self.kocom_scan = True
        self.scan_packet_buf = []

        self.tick = time.time()
        self.wp_list = {}
        self.wp_light = self.client._wp_light
        self.wp_fan = self.client._wp_fan
        self.wp_plug = self.client._wp_plug
        self.wp_gas = self.client._wp_gas
        self.wp_elevator = self.client._wp_elevator
        self.wp_thermostat = self.client._wp_thermostat
        for d_name in KOCOM_DEVICE.values():
            if d_name == Device.ELEVATOR or d_name == Device.GAS:
                self.wp_list[d_name] = {}
                self.wp_list[d_name][Device.WALLPAD] = {GeneralString.SCAN: {GeneralString.TICK: 0, GeneralString.COUNT: 0, GeneralString.LAST: 0}}
                self.wp_list[d_name][Device.WALLPAD][d_name] = {GeneralString.STATE: DeviceState.SWITCH_OFF, GeneralString.SET: DeviceState.SWITCH_OFF, GeneralString.LAST: GeneralString.STATE, GeneralString.COUNT: 0}
            elif d_name == Device.FAN:
                self.wp_list[d_name] = {}
                self.wp_list[d_name][Device.WALLPAD] = {GeneralString.SCAN: {GeneralString.TICK: 0, GeneralString.COUNT: 0, GeneralString.LAST: 0}}
                self.wp_list[d_name][Device.WALLPAD][GeneralString.MODE] = {GeneralString.STATE: DeviceState.SWITCH_OFF, GeneralString.SET: DeviceState.SWITCH_OFF, GeneralString.LAST: GeneralString.STATE, GeneralString.COUNT: 0}
                self.wp_list[d_name][Device.WALLPAD][GeneralString.SPEED] = {GeneralString.STATE: DeviceState.SWITCH_OFF, GeneralString.SET: DeviceState.SWITCH_OFF, GeneralString.LAST: GeneralString.STATE, GeneralString.COUNT: 0}
            elif d_name == Device.THERMOSTAT:
                self.wp_list[d_name] = {}
                for r_name in KOCOM_ROOM_THERMOSTAT.values():
                    self.wp_list[d_name][r_name] = {GeneralString.SCAN: {GeneralString.TICK: 0, GeneralString.COUNT: 0, GeneralString.LAST: 0}}
                    self.wp_list[d_name][r_name][GeneralString.MODE] = {GeneralString.STATE: 'off', GeneralString.SET: 'off', GeneralString.LAST: GeneralString.STATE, GeneralString.COUNT: 0}
                    self.wp_list[d_name][r_name][GeneralString.CURRENT_TEMP] = {GeneralString.STATE: 0, GeneralString.SET: 0, GeneralString.LAST: GeneralString.STATE, GeneralString.COUNT: 0}
                    self.wp_list[d_name][r_name][GeneralString.TARGET_TEMP] = {GeneralString.STATE: INIT_TEMP, GeneralString.SET: INIT_TEMP, GeneralString.LAST: GeneralString.STATE, GeneralString.COUNT: 0}
            elif d_name == Device.LIGHT or d_name == Device.PLUG:
                self.wp_list[d_name] = {}
                for r_name in KOCOM_ROOM.values():
                    self.wp_list[d_name][r_name] = {GeneralString.SCAN: {GeneralString.TICK: 0, GeneralString.COUNT: 0, GeneralString.LAST: 0}}
                    if d_name == Device.LIGHT:
                        for i in range(0, KOCOM_LIGHT_SIZE[r_name] + 1):
                            self.wp_list[d_name][r_name][d_name + str(i)] = {GeneralString.STATE: DeviceState.SWITCH_OFF, GeneralString.SET: DeviceState.SWITCH_OFF, GeneralString.LAST: GeneralString.STATE, GeneralString.COUNT: 0}
                    if d_name == Device.PLUG:
                        for i in range(0, KOCOM_PLUG_SIZE[r_name] + 1):
                            self.wp_list[d_name][r_name][d_name + str(i)] = {GeneralString.STATE: DeviceState.SWITCH_ON, GeneralString.SET: DeviceState.SWITCH_ON, GeneralString.LAST: GeneralString.STATE, GeneralString.COUNT: 0}

        self.d_type = client._type
        if self.d_type == ConfigValue.SERIAL:
            self.d_serial = client._connect[device]
        elif self.d_type == ConfigValue.SOCKET:
            self.d_serial = client._connect
        self.d_mqtt = self.connect_mqtt(self.client._mqtt, name)

        self._t1 = threading.Thread(target=self.get_serial, args=(name, packet_len))
        self._t1.start()
        self._t2 = threading.Thread(target=self.scan_list)
        self._t2.start()

    def connection_lost(self):
        self._t1.join()
        self._t2.join()
        if not self.connected:
            logger.debug('[ERROR] 서버 연결이 끊어져 kocom 클래스를 종료합니다.')
            return False

    def read(self):
        if self.client._connect == False:
            return ''
        try:
            if self.d_type == ConfigValue.SERIAL:
                if self.d_serial.readable():
                    return self.d_serial.read()
                else:
                    return ''
            elif self.d_type == ConfigValue.SOCKET:
                return self.d_serial.recv(1)
        except:
            logging.info('[Serial Read] Connection Error')

    def write(self, data):
        if data == False:
            return
        self.tick = time.time()
        if self.client._connect == False:
            return
        try:
            if self.d_type == ConfigValue.SERIAL:
                return self.d_serial.write(bytearray.fromhex((data)))
            elif self.d_type == ConfigValue.SOCKET:
                return self.d_serial.send(bytearray.fromhex((data)))
        except:
            logging.info('[Serial Write] Connection Error')

    def connect_mqtt(self, server, name):
        mqtt_client = mqtt.Client()
        mqtt_client.on_message = self.on_message
        #mqtt_client.on_publish = self.on_publish
        mqtt_client.on_subscribe = self.on_subscribe
        mqtt_client.on_connect = self.on_connect

        if server[ConfigField.ANONYMOUS] != BooleanString.TRUE:
            if server[ConfigField.SERVER] == '' or server[ConfigField.USERNAME] == '' or server[ConfigField.PASSWORD] == '':
                logger.info('{} 설정을 확인하세요. Server[{}] ID[{}] PW[{}] Device[{}]'.format(ConfigField.MQTT, server[ConfigField.SERVER], server[ConfigField.USRENAME], server[ConfigField.PASSWORD], name))
                return False
            mqtt_client.username_pw_set(username=server[ConfigField.USERNAME], password=server[ConfigField.PASSWORD])
            logger.debug('{} STATUS. Server[{}] ID[{}] PW[{}] Device[{}]'.format(ConfigField.MQTT, server[ConfigField.SERVER], server[ConfigField.USERNAME], server[ConfigField.PASSWORD], name))
        else:
            logger.debug('{} STATUS. Server[{}] Device[{}]'.format(ConfigField.MQTT, server[ConfigField.SERVER], name))

        mqtt_client.connect(server[ConfigField.SERVER], 1883, 60)
        mqtt_client.loop_start()
        return mqtt_client

    def on_message(self, client, obj, msg):
        _topic = msg.topic.split('/')
        _payload = msg.payload.decode()

        if GeneralString.CONFIG in _topic and _topic[0] == GeneralString.RS485 and _topic[1] == GeneralString.BRIDGE and _topic[2] == GeneralString.CONFIG:
            if _topic[3] == GeneralString.LOG_LEVEL:
                if _payload == LogLevel.INFO: logger.setLevel(logging.INFO)
                if _payload == LogLevel.DEBUG: logger.setLevel(logging.DEBUG)
                if _payload == LogLevel.WARN: logger.setLevel(logging.WARN)
                logger.info('[From HA]Set Loglevel to {}'.format(_payload))
                return
            elif _topic[3] == GeneralString.RESTART:
                self.homeassistant_device_discovery()
                logger.info('[From HA]HomeAssistant Restart')
                return
            elif _topic[3] == GeneralString.REMOVE:
                self.homeassistant_device_discovery(remove=True)
                logger.info('[From HA]HomeAssistant Remove')
                return
            elif _topic[3] == GeneralString.SCAN:
                for d_name in KOCOM_DEVICE.values():
                    if d_name == Device.ELEVATOR or d_name == Device.GAS:
                        self.wp_list[d_name][Device.WALLPAD] = {GeneralString.SCAN: {GeneralString.TICK: 0, GeneralString.COUNT: 0, GeneralString.LAST: 0}}
                    elif d_name == Device.FAN:
                        self.wp_list[d_name][Device.WALLPAD] = {GeneralString.SCAN: {GeneralString.TICK: 0, GeneralString.COUNT: 0, GeneralString.LAST: 0}}
                    elif d_name == Device.THERMOSTAT:
                        for r_name in KOCOM_ROOM_THERMOSTAT.values():
                            self.wp_list[d_name][r_name] = {GeneralString.SCAN: {GeneralString.TICK: 0, GeneralString.COUNT: 0, GeneralString.LAST: 0}}
                    elif d_name == Device.LIGHT or d_name == Device.PLUG:
                        for r_name in KOCOM_ROOM.values():
                            self.wp_list[d_name][r_name] = {GeneralString.SCAN: {GeneralString.TICK: 0, GeneralString.COUNT: 0, GeneralString.LAST: 0}}
                logger.info('[From HA]HomeAssistant Scan')
                return
            elif _topic[3] == GeneralString.PACKET:
                self.packet_parsing(_payload.lower(), name=GeneralString.NAME_HA)
            elif _topic[3] == GeneralString.CHECKSUM:
                chksum = self.check_sum(_payload.lower())
                logger.info('[From HA]{} = {}({})'.format(_payload, chksum[0], chksum[1]))
        elif not self.kocom_scan:
            self.parse_message(_topic, _payload)
            return
        logger.info("Message: {} = {}".format(msg.topic, _payload))

        if self.ha_registry != False and self.ha_registry == msg.topic and self.kocom_scan:
            self.kocom_scan = False

    def parse_message(self, topic, payload):
        device = topic[1]
        command = topic[3]
        if device == HAStrings.LIGHT or device == HAStrings.SWITCH:
            room_device = topic[2].split('_')
            room = room_device[0]
            sub_device = room_device[1]
            for dev in [Device.LIGHT, Device.PLUG, Device.ELEVATOR, Device.GAS]:
                if sub_device.find(dev) != -1:
                    device = dev
                    break

            try:
                if device == Device.GAS:
                    if payload == DeviceState.SWITCH_ON:
                        payload =DeviceState.SWITCH_OFF
                        logger.info('[From HA]Error GAS Cannot Set to ON')
                    else:
                        self.wp_list[device][room][sub_device][command] = payload
                        self.wp_list[device][room][sub_device][GeneralString.LAST] = command
                elif device == Device.ELEVATOR:
                    if payload == DeviceState.SWITCH_OFF:
                        self.wp_list[device][room][sub_device][command] = payload
                        self.wp_list[device][room][sub_device][GeneralString.LAST] = GeneralString.STATE
                        self.send_to_homeassistant(device, Device.WALLPAD, payload)
                    else:
                        self.wp_list[device][room][sub_device][command] = payload
                        self.wp_list[device][room][sub_device][GeneralString.LAST] = command
                else:
                    self.wp_list[device][room][sub_device][command] = payload
                    self.wp_list[device][room][sub_device][GeneralString.LAST] = command
                logger.info('[From HA]{}/{}/{}/{} = {}'.format(device, room, sub_device, command, payload))
            except:
                logger.info('[From HA]Error {} = {}'.format(topic, payload))
        elif device == HAStrings.CLIMATE:
            device = Device.THERMOSTAT
            room = topic[2]
            try:
                if command != GeneralString.MODE:
                    self.wp_list[device][room][GeneralString.TARGET_TEMP][GeneralString.SET] = int(float(payload))
                    self.wp_list[device][room][GeneralString.MODE][GeneralString.SET] = GeneralString.HEAT
                    self.wp_list[device][room][GeneralString.TARGET_TEMP][GeneralString.LAST] = GeneralString.SET
                    self.wp_list[device][room][GeneralString.MODE][GeneralString.LAST] = GeneralString.SET
                else:
                    self.wp_list[device][room][GeneralString.MODE][GeneralString.SET] = payload
                    self.wp_list[device][room][GeneralString.MODE][GeneralString.LAST] = GeneralString.SET
                ha_payload = {
                    GeneralString.MODE: self.wp_list[device][room][GeneralString.MODE][GeneralString.SET],
                    GeneralString.TARGET_TEMP: self.wp_list[device][room][GeneralString.TARGET_TEMP][GeneralString.SET],
                    GeneralString.CURRENT_TEMP: self.wp_list[device][room][GeneralString.CURRENT_TEMP][GeneralString.STATE]
                }
                logger.info('[From HA]{}/{}/set = [mode={}, target_temp={}]'.format(device, room, self.wp_list[device][room][GeneralString.MODE][GeneralString.SET], self.wp_list[device][room][GeneralString.TARGET_TEMP][GeneralString.SET]))
                self.send_to_homeassistant(device, room, ha_payload)
            except:
                logger.info('[From HA]Error {} = {}'.format(topic, payload))
        elif device == HAStrings.FAN:
            device = Device.FAN
            room = topic[2]
            try:
                if command != GeneralString.MODE:
                    self.wp_list[device][room][GeneralString.SPEED][GeneralString.SET] = payload
                    self.wp_list[device][room][GeneralString.MODE][GeneralString.SET] = DeviceState.SWITCH_ON
                elif command == GeneralString.MODE:
                    self.wp_list[device][room][GeneralString.SPEED][GeneralString.SET] = DEFAULT_SPEED if payload == DeviceState.SWITCH_ON else DeviceState.SWITCH_OFF
                    self.wp_list[device][room][GeneralString.MODE][GeneralString.SET] = payload
                self.wp_list[device][room][GeneralString.SPEED][GeneralString.LAST] = GeneralString.SET
                self.wp_list[device][room][GeneralString.MODE][GeneralString.LAST] = GeneralString.SET
                ha_payload = {
                    GeneralString.MODE: self.wp_list[device][room][GeneralString.MODE][GeneralString.SET],
                    GeneralString.SPEED: self.wp_list[device][room][GeneralString.SPEED][GeneralString.SET]
                }
                logger.info('[From HA]{}/{}/set = [mode={}, speed={}]'.format(device, room, self.wp_list[device][room][GeneralString.MODE][GeneralString.SET], self.wp_list[device][room][GeneralString.SPEED][GeneralString.SET]))
                self.send_to_homeassistant(device, room, ha_payload)
            except:
                logger.info('[From HA]Error {} = {}'.format(topic, payload))

    def on_publish(self, client, obj, mid):
        logger.info("Publish: {}".format(str(mid)))

    def on_subscribe(self, client, obj, mid, granted_qos):
        logger.info("Subscribed: {} {}".format(str(mid),str(granted_qos)))

    def on_connect(self, client, userdata, flags, rc):
        if int(rc) == 0:
            logger.info("[MQTT] connected OK")
            self.homeassistant_device_discovery(initial=True)
        elif int(rc) == 1:
            logger.info("[MQTT] 1: Connection refused – incorrect protocol version")
        elif int(rc) == 2:
            logger.info("[MQTT] 2: Connection refused – invalid client identifier")
        elif int(rc) == 3:
            logger.info("[MQTT] 3: Connection refused – server unavailable")
        elif int(rc) == 4:
            logger.info("[MQTT] 4: Connection refused – bad username or password")
        elif int(rc) == 5:
            logger.info("[MQTT] 5: Connection refused – not authorised")
        else:
            logger.info("[MQTT] {} : Connection refused".format(rc))

    def homeassistant_device_discovery(self, initial=False, remove=False):
        subscribe_list = []
        subscribe_list.append(('rs485/bridge/#', 0))
        publish_list = []

        self.ha_registry = False
        self.kocom_scan = True

        if self.wp_elevator:
            ha_topic = '{}/{}/{}_{}/config'.format(HAStrings.PREFIX, HAStrings.SWITCH, Device.WALLPAD, Device.ELEVATOR)
            ha_payload = {
                'name': '{}_{}_{}'.format(self._name, Device.WALLPAD, Device.ELEVATOR),
                'cmd_t': '{}/{}/{}_{}/set'.format(HAStrings.PREFIX, HAStrings.SWITCH, Device.WALLPAD, Device.ELEVATOR),
                'stat_t': '{}/{}/{}/state'.format(HAStrings.PREFIX, HAStrings.SWITCH, Device.WALLPAD),
                'val_tpl': '{{ value_json.' + Device.ELEVATOR + ' }}',
                'ic': 'mdi:elevator',
                'pl_on': 'on',
                'pl_off': 'off',
                'uniq_id': '{}_{}_{}'.format(self._name, Device.WALLPAD, Device.ELEVATOR),
                'device': {
                    'name': 'Kocom {}'.format(Device.WALLPAD),
                    'ids': 'kocom_{}'.format(Device.WALLPAD),
                    'mf': GeneralString.KOCOM,
                    'mdl': Device.WALLPAD,
                    'sw': SW_VERSION
                }
            }
            subscribe_list.append((ha_topic, 0))
            subscribe_list.append((ha_payload['cmd_t'], 0))
            #subscribe_list.append((ha_payload['stat_t'], 0))
            if remove:
                publish_list.append({ha_topic : ''})
            else:
                publish_list.append({ha_topic : json.dumps(ha_payload)})
        if self.wp_gas:
            ha_topic = '{}/{}/{}_{}/config'.format(HAStrings.PREFIX, HAStrings.SWITCH, Device.WALLPAD, Device.GAS)
            ha_payload = {
                'name': '{}_{}_{}'.format(self._name, Device.WALLPAD, Device.GAS),
                'cmd_t': '{}/{}/{}_{}/set'.format(HAStrings.PREFIX, HAStrings.SWITCH, Device.WALLPAD, Device.GAS),
                'stat_t': '{}/{}/{}_{}/state'.format(HAStrings.PREFIX, HAStrings.SWITCH, Device.WALLPAD, Device.GAS),
                'val_tpl': '{{ value_json.' + Device.GAS + ' }}',
                'ic': 'mdi:gas-cylinder',
                'pl_on': 'on',
                'pl_off': 'off',
                'uniq_id': '{}_{}_{}'.format(self._name, Device.WALLPAD, Device.GAS),
                'device': {
                    'name': 'Kocom {}'.format(Device.WALLPAD),
                    'ids': 'kocom_{}'.format(Device.WALLPAD),
                    'mf': GeneralString.KOCOM,
                    'mdl': Device.WALLPAD,
                    'sw': SW_VERSION
                }
            }
            subscribe_list.append((ha_topic, 0))
            subscribe_list.append((ha_payload['cmd_t'], 0))
            #subscribe_list.append((ha_payload['stat_t'], 0))
            if remove:
                publish_list.append({ha_topic : ''})
            else:
                publish_list.append({ha_topic : json.dumps(ha_payload)})

            ha_topic = '{}/{}/{}_{}/config'.format(HAStrings.PREFIX, HAStrings.SENSOR, Device.WALLPAD, Device.GAS)
            ha_payload = {
                'name': '{}_{}_{}'.format(self._name, Device.WALLPAD, Device.GAS),
                'stat_t': '{}/{}/{}_{}/state'.format(HAStrings.PREFIX, HAStrings.SENSOR, Device.WALLPAD, Device.GAS),
                'val_tpl': '{{ value_json.' + Device.GAS + ' }}',
                'ic': 'mdi:gas-cylinder',
                'uniq_id': '{}_{}_{}'.format(self._name, Device.WALLPAD, Device.GAS),
                'device': {
                    'name': 'Kocom {}'.format(Device.WALLPAD),
                    'ids': 'kocom_{}'.format(Device.WALLPAD),
                    'mf': GeneralString.KOCOM,
                    'mdl': Device.WALLPAD,
                    'sw': SW_VERSION
                }
            }
            subscribe_list.append((ha_topic, 0))
            #subscribe_list.append((ha_payload['stat_t'], 0))
            publish_list.append({ha_topic : json.dumps(ha_payload)})
        if self.wp_fan:
            ha_topic = '{}/{}/{}_{}/config'.format(HAStrings.PREFIX, HAStrings.FAN, Device.WALLPAD, Device.FAN)
            ha_payload = {
                'name': '{}_{}_{}'.format(self._name, Device.WALLPAD, Device.FAN),
                'cmd_t': '{}/{}/{}/mode'.format(HAStrings.PREFIX, HAStrings.FAN, Device.WALLPAD),
                'stat_t': '{}/{}/{}/state'.format(HAStrings.PREFIX, HAStrings.FAN, Device.WALLPAD),
                'spd_cmd_t': '{}/{}/{}/speed'.format(HAStrings.PREFIX, HAStrings.FAN, Device.WALLPAD),
                'spd_stat_t': '{}/{}/{}/state'.format(HAStrings.PREFIX, HAStrings.FAN, Device.WALLPAD),
                'stat_val_tpl': '{{ value_json.mode }}',
                'spd_val_tpl': '{{ value_json.speed }}',
                'pl_on': 'on',
                'pl_off': 'off',
                'spds': ['low', 'medium', 'high', 'off'],
                'uniq_id': '{}_{}_{}'.format(self._name, Device.WALLPAD, Device.FAN),
                'device': {
                    'name': 'Kocom {}'.format(Device.WALLPAD),
                    'ids': 'kocom_{}'.format(Device.WALLPAD),
                    'mf': GeneralString.KOCOM,
                    'mdl': Device.WALLPAD,
                    'sw': SW_VERSION
                }
            }
            subscribe_list.append((ha_topic, 0))
            subscribe_list.append((ha_payload['cmd_t'], 0))
            #subscribe_list.append((ha_payload['stat_t'], 0))
            subscribe_list.append((ha_payload['spd_cmd_t'], 0))
            if remove:
                publish_list.append({ha_topic : ''})
            else:
                publish_list.append({ha_topic : json.dumps(ha_payload)})
        if self.wp_light:
            for room, r_value in self.wp_list[Device.LIGHT].items():
                if type(r_value) == dict:
                    for sub_device, d_value in r_value.items():
                        if type(d_value) == dict:
                            ha_topic = '{}/{}/{}_{}/config'.format(HAStrings.PREFIX, HAStrings.LIGHT, room, sub_device)
                            ha_payload = {
                                'name': '{}_{}_{}'.format(self._name, room, sub_device),
                                'cmd_t': '{}/{}/{}_{}/set'.format(HAStrings.PREFIX, HAStrings.LIGHT, room, sub_device),
                                'stat_t': '{}/{}/{}/state'.format(HAStrings.PREFIX, HAStrings.LIGHT, room),
                                'val_tpl': '{{ value_json.' + str(sub_device) + ' }}',
                                'pl_on': 'on',
                                'pl_off': 'off',
                                'uniq_id': '{}_{}_{}'.format(self._name, room, sub_device),
                                'device': {
                                    'name': 'Kocom {}'.format(room),
                                    'ids': 'kocom_{}'.format(room),
                                    'mf': GeneralString.KOCOM,
                                    'mdl': Device.WALLPAD,
                                    'sw': SW_VERSION
                                }
                            }
                            subscribe_list.append((ha_topic, 0))
                            subscribe_list.append((ha_payload['cmd_t'], 0))
                            #subscribe_list.append((ha_payload['stat_t'], 0))
                            if remove:
                                publish_list.append({ha_topic : ''})
                            else:
                                publish_list.append({ha_topic : json.dumps(ha_payload)})
        if self.wp_plug:
            for room, r_value in self.wp_list[Device.PLUG].items():
                if type(r_value) == dict:
                    for sub_device, d_value in r_value.items():
                        if type(d_value) == dict:
                            ha_topic = '{}/{}/{}_{}/config'.format(HAStrings.PREFIX, HAStrings.SWITCH, room, sub_device)
                            ha_payload = {
                                'name': '{}_{}_{}'.format(self._name, room, sub_device),
                                'cmd_t': '{}/{}/{}_{}/set'.format(HAStrings.PREFIX, HAStrings.SWITCH, room, sub_device),
                                'stat_t': '{}/{}/{}/state'.format(HAStrings.PREFIX, HAStrings.SWITCH, room),
                                'val_tpl': '{{ value_json.' + str(sub_device) + ' }}',
                                'ic': 'mdi:power-socket-eu',
                                'pl_on': 'on',
                                'pl_off': 'off',
                                'uniq_id': '{}_{}_{}'.format(self._name, room, sub_device),
                                'device': {
                                    'name': 'Kocom {}'.format(room),
                                    'ids': 'kocom_{}'.format(room),
                                    'mf': GeneralString.KOCOM,
                                    'mdl': Device.WALLPAD,
                                    'sw': SW_VERSION
                                }
                            }
                            subscribe_list.append((ha_topic, 0))
                            subscribe_list.append((ha_payload['cmd_t'], 0))
                            #subscribe_list.append((ha_payload['stat_t'], 0))
                            if remove:
                                publish_list.append({ha_topic : ''})
                            else:
                                publish_list.append({ha_topic : json.dumps(ha_payload)})
        if self.wp_thermostat:
            for room, r_list in self.wp_list[Device.THERMOSTAT].items():
                if type(r_list) == dict:
                    ha_topic = '{}/{}/{}/config'.format(HAStrings.PREFIX, HAStrings.CLIMATE, room)
                    ha_payload = {
                        'name': '{}_{}_{}'.format(self._name, room, Device.THERMOSTAT),
                        'mode_cmd_t': '{}/{}/{}/mode'.format(HAStrings.PREFIX, HAStrings.CLIMATE, room),
                        'mode_stat_t': '{}/{}/{}/state'.format(HAStrings.PREFIX, HAStrings.CLIMATE, room),
                        'mode_stat_tpl': '{{ value_json.mode }}',
                        'temp_cmd_t': '{}/{}/{}/target_temp'.format(HAStrings.PREFIX, HAStrings.CLIMATE, room),
                        'temp_stat_t': '{}/{}/{}/state'.format(HAStrings.PREFIX, HAStrings.CLIMATE, room),
                        'temp_stat_tpl': '{{ value_json.target_temp }}',
                        'curr_temp_t': '{}/{}/{}/state'.format(HAStrings.PREFIX, HAStrings.CLIMATE, room),
                        'curr_temp_tpl': '{{ value_json.current_temp }}',
                        'min_temp': 5,
                        'max_temp': 40,
                        'temp_step': 1,
                        'modes': ['off', 'heat', 'fan_only'],
                        'uniq_id': '{}_{}_{}'.format(self._name, room, Device.THERMOSTAT),
                        'device': {
                            'name': 'Kocom {}'.format(room),
                            'ids': 'kocom_{}'.format(room),
                            'mf': GeneralString.KOCOM,
                            'mdl': Device.WALLPAD,
                            'sw': SW_VERSION
                        }
                    }
                    subscribe_list.append((ha_topic, 0))
                    subscribe_list.append((ha_payload['mode_cmd_t'], 0))
                    #subscribe_list.append((ha_payload['mode_stat_t'], 0))
                    subscribe_list.append((ha_payload['temp_cmd_t'], 0))
                    #subscribe_list.append((ha_payload['temp_stat_t'], 0))
                    if remove:
                        publish_list.append({ha_topic : ''})
                    else:
                        publish_list.append({ha_topic : json.dumps(ha_payload)})

        if initial:
            self.d_mqtt.subscribe(subscribe_list)
        for ha in publish_list:
            for topic, payload in ha.items():
                self.d_mqtt.publish(topic, payload)
        self.ha_registry = ha_topic

    def send_to_homeassistant(self, device, room, value):
        v_value = json.dumps(value)
        if device == Device.LIGHT:
            self.d_mqtt.publish("{}/{}/{}/state".format(HAStrings.PREFIX, HAStrings.LIGHT, room), v_value)
            logger.info("[To HA]{}/{}/{}/state = {}".format(HAStrings.PREFIX, HAStrings.LIGHT, room, v_value))
        elif device == Device.PLUG:
            self.d_mqtt.publish("{}/{}/{}/state".format(HAStrings.PREFIX, HAStrings.SWITCH, room), v_value)
            logger.info("[To HA]{}/{}/{}/state = {}".format(HAStrings.PREFIX, HAStrings.SWITCH, room, v_value))
        elif device == Device.THERMOSTAT:
            self.d_mqtt.publish("{}/{}/{}/state".format(HAStrings.PREFIX, HAStrings.CLIMATE, room), v_value)
            logger.info("[To HA]{}/{}/{}/state = {}".format(HAStrings.PREFIX, HAStrings.CLIMATE, room, v_value))
        elif device == Device.ELEVATOR:
            v_value = json.dumps({device: value})
            self.d_mqtt.publish("{}/{}/{}/state".format(HAStrings.PREFIX, HAStrings.SWITCH, room), v_value)
            logger.info("[To HA]{}/{}/{}/state = {}".format(HAStrings.PREFIX, HAStrings.SWITCH, room, v_value))
        elif device == Device.GAS:
            v_value = json.dumps({device: value})
            self.d_mqtt.publish("{}/{}/{}_{}/state".format(HAStrings.PREFIX, HAStrings.SENSOR, room, Device.GAS), v_value)
            logger.info("[To HA]{}/{}/{}_{}/state = {}".format(HAStrings.PREFIX, HAStrings.SENSOR, room, Device.GAS, v_value))
            self.d_mqtt.publish("{}/{}/{}_{}/state".format(HAStrings.PREFIX, HAStrings.SWITCH, room, Device.GAS), v_value)
            logger.info("[To HA]{}/{}/{}_{}/state = {}".format(HAStrings.PREFIX, HAStrings.SWITCH, room, Device.GAS, v_value))
        elif device == Device.FAN:
            self.d_mqtt.publish("{}/{}/{}/state".format(HAStrings.PREFIX, HAStrings.FAN, room), v_value)
            logger.info("[To HA]{}/{}/{}/state = {}".format(HAStrings.PREFIX, HAStrings.FAN, room, v_value))

    def get_serial(self, packet_name, packet_len):
        packet = ''
        start_flag = False
        while True:
            row_data = self.read()
            hex_d = row_data.hex()
            start_hex = ''
            if packet_name == GeneralString.KOCOM:  start_hex = 'aa'
            elif packet_name == 'grex_ventilator':  start_hex = 'd1'
            elif packet_name == 'grex_controller':  start_hex = 'd0'
            if hex_d == start_hex:
                start_flag = True
            if start_flag:
                packet += hex_d

            if len(packet) >= packet_len:
                chksum = self.check_sum(packet)
                if chksum[0]:
                    self.tick = time.time()
                    logger.debug("[From {}]{}".format(packet_name, packet))
                    self.packet_parsing(packet)
                packet = ''
                start_flag = False
            if not self.connected:
                logger.debug('[ERROR] 서버 연결이 끊어져 get_serial Thread를 종료합니다.')
                break

    def check_sum(self, packet):
        sum_packet = sum(bytearray.fromhex(packet)[:17])
        v_sum = int(packet[34:36], 16) if len(packet) >= 36 else 0
        chk_sum = '{0:02x}'.format((sum_packet + 1 + v_sum) % 256)
        orgin_sum = packet[36:38] if len(packet) >= 38 else ''
        return (True, chk_sum) if chk_sum == orgin_sum else (False, chk_sum)

    def parse_packet(self, packet):
        p = {}
        try:
            p['header'] = packet[:4]
            p['type'] = packet[4:7]
            p['order'] = packet[7:8]
            if KOCOM_TYPE.get(p['type']) == 'send':
                p['dst_device'] = packet[10:12]
                p['dst_room'] = packet[12:14]
                p['src_device'] = packet[14:16]
                p['src_room'] = packet[16:18]
            elif KOCOM_TYPE.get(p['type']) == 'ack':
                p['src_device'] = packet[10:12]
                p['src_room'] = packet[12:14]
                p['dst_device'] = packet[14:16]
                p['dst_room'] = packet[16:18]
            p['command'] = packet[18:20]
            p['value'] = packet[20:36]
            p['checksum'] = packet[36:38]
            p['tail'] = packet[38:42]
            return p
        except:
            return False

    def value_packet(self, p):
        v = {}
        if not p:
            return False
        try:
            v['type'] = KOCOM_TYPE.get(p['type'])
            v['command'] = KOCOM_COMMAND.get(p['command'])
            v['src_device'] = KOCOM_DEVICE.get(p['src_device'])
            v['src_room'] = KOCOM_ROOM.get(p['src_room']) if v['src_device'] != Device.THERMOSTAT else KOCOM_ROOM_THERMOSTAT.get(p['src_room'])
            v['dst_device'] = KOCOM_DEVICE.get(p['dst_device'])
            v['dst_room'] = KOCOM_ROOM.get(p['dst_room']) if v['src_device'] != Device.THERMOSTAT else KOCOM_ROOM_THERMOSTAT.get(p['dst_room'])
            v['value'] = p['value']
            if v['src_device'] == Device.FAN:
                v['value'] = self.parse_fan(p['value'])
            elif v['src_device'] == Device.LIGHT or v['src_device'] == Device.PLUG:
                v['value'] = self.parse_switch(v['src_device'], v['src_room'], p['value'])
            elif v['src_device'] == Device.THERMOSTAT:
                v['value'] = self.parse_thermostat(p['value'], self.wp_list[v['src_device']][v['src_room']][GeneralString.TARGET_TEMP][GeneralString.STATE])
            elif v['src_device'] == Device.WALLPAD and v['dst_device'] == Device.ELEVATOR:
                v['value'] = 'off'
            elif v['src_device'] == Device.GAS:
                v['value'] = v['command']
            return v
        except:
            return False

    def packet_parsing(self, packet, name=GeneralString.KOCOM, from_to='From'):
        p = self.parse_packet(packet)
        v = self.value_packet(p)

        try:
            if v['command'] == CommandStr.QUERY and v['src_device'] == Device.WALLPAD:
                if name == GeneralString.NAME_HA:
                    self.write(self.make_packet(v['dst_device'], v['dst_room'], CommandStr.QUERY, '', ''))
                logger.debug('[{} {}]{}({}) {}({}) -> {}({})'.format(from_to, name, v['type'], v['command'], v['src_device'], v['src_room'], v['dst_device'], v['dst_room']))
            else:
                logger.debug('[{} {}]{}({}) {}({}) -> {}({}) = {}'.format(from_to, name, v['type'], v['command'], v['src_device'], v['src_room'], v['dst_device'], v['dst_room'], v['value']))

            if (v['type'] == 'ack' and v['dst_device'] == Device.WALLPAD) or (v['type'] == 'send' and v['dst_device'] == Device.ELEVATOR):
                if v['type'] == 'send' and v['dst_device'] == Device.ELEVATOR:
                    self.set_list(v['dst_device'], Device.WALLPAD, v['value'])
                    self.send_to_homeassistant(v['dst_device'], Device.WALLPAD, v['value'])
                elif v['src_device'] == Device.FAN or v['src_device'] == Device.GAS:
                    self.set_list(v['src_device'], Device.WALLPAD, v['value'])
                    self.send_to_homeassistant(v['src_device'], Device.WALLPAD, v['value'])
                elif v['src_device'] == Device.THERMOSTAT or v['src_device'] == Device.LIGHT or v['src_device'] == Device.PLUG:
                    self.set_list(v['src_device'], v['src_room'], v['value'])
                    self.send_to_homeassistant(v['src_device'], v['src_room'], v['value'])
        except:
            logger.info('[{} {}]Error {}'.format(from_to, name, packet))

    def set_list(self, device, room, value, name=GeneralString.KOCOM):
        try:
            logger.info('[From {}]{}/{}/state = {}'.format(name, device, room, value))
            if GeneralString.SCAN in self.wp_list[device][room] and type(self.wp_list[device][room][GeneralString.SCAN]) == dict:
                self.wp_list[device][room][GeneralString.SCAN][GeneralString.TICK] = time.time()
                self.wp_list[device][room][GeneralString.SCAN][GeneralString.COUNT] = 0
                self.wp_list[device][room][GeneralString.SCAN][GeneralString.LAST] = 0
            if device == Device.GAS or device == Device.ELEVATOR:
                self.wp_list[device][room][device][GeneralString.STATE] = value
                self.wp_list[device][room][device][GeneralString.LAST] = GeneralString.STATE
                self.wp_list[device][room][device][GeneralString.COUNT] = 0
            elif device == Device.FAN:
                for sub, v in value.items():
                    try:
                        if sub == GeneralString.MODE:
                            self.wp_list[device][room][sub][GeneralString.STATE] = v
                            self.wp_list[device][room][GeneralString.SPEED][GeneralString.STATE] = 'off' if v == 'off' else DEFAULT_SPEED
                        else:
                            self.wp_list[device][room][sub][GeneralString.STATE] = v
                            self.wp_list[device][room][GeneralString.MODE][GeneralString.STATE] = 'off' if v == 'off' else 'on'
                        if (self.wp_list[device][room][sub][GeneralString.LAST] == GeneralString.SET or type(self.wp_list[device][room][sub][GeneralString.LAST]) == float) and self.wp_list[device][room][sub][GeneralString.SET] == self.wp_list[device][room][sub][GeneralString.STATE]:
                            self.wp_list[device][room][sub][GeneralString.LAST] = GeneralString.STATE
                            self.wp_list[device][room][sub][GeneralString.COUNT] = 0
                    except:
                        logger.info('[From {}]Error SetListDevice {}/{}/{}/state = {}'.format(name, device, room, sub, v))
            elif device == Device.LIGHT or device == Device.PLUG:
                for sub, v in value.items():
                    try:
                        self.wp_list[device][room][sub][GeneralString.STATE] = v
                        if (self.wp_list[device][room][sub][GeneralString.LAST] == GeneralString.SET or type(self.wp_list[device][room][sub][GeneralString.LAST]) == float) and self.wp_list[device][room][sub][GeneralString.SET] == self.wp_list[device][room][sub][GeneralString.STATE]:
                            self.wp_list[device][room][sub][GeneralString.LAST] = GeneralString.STATE
                            self.wp_list[device][room][sub][GeneralString.COUNT] = 0
                    except:
                        logger.info('[From {}]Error SetListDevice {}/{}/{}/state = {}'.format(name, device, room, sub, v))
            elif device == Device.THERMOSTAT:
                for sub, v in value.items():
                    try:
                        if sub == GeneralString.MODE:
                            self.wp_list[device][room][sub][GeneralString.STATE] = v
                        else:
                            self.wp_list[device][room][sub][GeneralString.STATE] = int(float(v))
                            self.wp_list[device][room][GeneralString.MODE][GeneralString.STATE] = 'heat'
                        if (self.wp_list[device][room][sub][GeneralString.LAST] == GeneralString.SET or type(self.wp_list[device][room][sub][GeneralString.LAST]) == float) and self.wp_list[device][room][sub][GeneralString.SET] == self.wp_list[device][room][sub][GeneralString.STATE]:
                            self.wp_list[device][room][sub][GeneralString.LAST] = GeneralString.STATE
                            self.wp_list[device][room][sub][GeneralString.COUNT] = 0
                    except:
                        logger.info('[From {}]Error SetListDevice {}/{}/{}/state = {}'.format(name, device, room, sub, v))
        except:
            logger.info('[From {}]Error SetList {}/{} = {}'.format(name, device, room, value))

    def scan_list(self):
        while True:
            if not self.kocom_scan:
                now = time.time()
                if now - self.tick > KOCOM_INTERVAL / 1000:
                    try:
                        for device, d_list in self.wp_list.items():
                            if type(d_list) == dict and ((device == Device.ELEVATOR and self.wp_elevator) or (device == Device.FAN and self.wp_fan) or (device == Device.GAS and self.wp_gas) or (device == Device.LIGHT and self.wp_light) or (device == Device.PLUG and self.wp_plug) or (device == Device.THERMOSTAT and self.wp_thermostat)):
                                for room, r_list in d_list.items():
                                    if type(r_list) == dict:
                                        if GeneralString.SCAN in r_list and type(r_list[GeneralString.SCAN]) == dict and now - r_list[GeneralString.SCAN][GeneralString.TICK] > SCAN_INTERVAL and ((device == Device.FAN and self.wp_fan) or (device == Device.GAS and self.wp_gas) or (device == Device.LIGHT and self.wp_light) or (device == Device.PLUG and self.wp_plug) or (device == Device.THERMOSTAT and self.wp_thermostat)):
                                            if now - r_list[GeneralString.SCAN][GeneralString.LAST] > 2:
                                                r_list[GeneralString.SCAN][GeneralString.COUNT] += 1
                                                r_list[GeneralString.SCAN][GeneralString.LAST] = now
                                                self.set_serial(device, room, '', '', cmd=CommandStr.QUERY)
                                                time.sleep(SCANNING_INTERVAL)
                                            if r_list[GeneralString.SCAN][GeneralString.COUNT] > 4:
                                                r_list[GeneralString.SCAN][GeneralString.TICK] = now
                                                r_list[GeneralString.SCAN][GeneralString.COUNT] = 0
                                                r_list[GeneralString.SCAN][GeneralString.LAST] = 0
                                        else:
                                            for sub_d, sub_v in r_list.items():
                                                if sub_d != GeneralString.SCAN:
                                                    if sub_v[GeneralString.COUNT] > 4:
                                                        sub_v[GeneralString.COUNT] = 0
                                                        sub_v[GeneralString.LAST] = GeneralString.STATE
                                                    elif sub_v[GeneralString.LAST] == GeneralString.SET:
                                                        sub_v[GeneralString.LAST] = now
                                                        if device == Device.GAS:
                                                            sub_v[GeneralString.LAST] += 5
                                                        elif device == Device.ELEVATOR:
                                                            sub_v[GeneralString.LAST] = GeneralString.STATE
                                                        self.set_serial(device, room, sub_d, sub_v[GeneralString.SET])
                                                    elif type(sub_v[GeneralString.LAST]) == float and now - sub_v[GeneralString.LAST] > 1:
                                                        sub_v[GeneralString.LAST] = GeneralString.SET
                                                        sub_v[GeneralString.COUNT] += 1
                    except:
                        logger.debug('[Scan]Error')
            if not self.connected:
                logger.debug('[ERROR] 서버 연결이 끊어져 scan_list Thread를 종료합니다.')
                break
            time.sleep(0.2)

    def set_serial(self, device, room, target, value, cmd=CommandStr.STATUS):
        if (time.time() - self.tick) < KOCOM_INTERVAL / 1000:
            return
        if cmd == CommandStr.STATUS:
            logger.info('[To {}]{}/{}/{} -> {}'.format(self._name, device, room, target, value))
        elif cmd == CommandStr.QUERY:
            logger.info('[To {}]{}/{} -> 조회'.format(self._name, device, room))
        packet = self.make_packet(device, room, CommandStr.STATUS, target, value) if cmd == CommandStr.STATUS else  self.make_packet(device, room, CommandStr.QUERY, '', '')
        v = self.value_packet(self.parse_packet(packet))

        logger.debug('[To {}]{}'.format(self._name, packet))
        if v['command'] == "조회" and v['src_device'] == Device.WALLPAD:
            logger.debug('[To {}]{}({}) {}({}) -> {}({})'.format(self._name, v['type'], v['command'], v['src_device'], v['src_room'], v['dst_device'], v['dst_room']))
        else:
            logger.debug('[To {}]{}({}) {}({}) -> {}({}) = {}'.format(self._name, v['type'], v['command'], v['src_device'], v['src_room'], v['dst_device'], v['dst_room'], v['value']))
        if device == Device.ELEVATOR:
            self.send_to_homeassistant(Device.ELEVATOR, Device.WALLPAD, 'on')
        self.write(packet)

    def make_packet(self, device, room, cmd, target, value):
        p_header = 'aa5530bc00'
        p_device = KOCOM_DEVICE_REV.get(device)
        p_room = KOCOM_ROOM_REV.get(room) if device != Device.THERMOSTAT else  KOCOM_ROOM_THERMOSTAT_REV.get(room)
        p_dst = KOCOM_DEVICE_REV.get(Device.WALLPAD) + KOCOM_ROOM_REV.get(Device.WALLPAD)
        p_cmd = KOCOM_COMMAND_REV.get(cmd)
        p_value = ''

        if room is Room.MASTER_LIGHT:
            p_cmd = KOCOM_COMMAND_REV.get(CommandStr.MASTER_LIGHT_OFF) if cmd == CommandStr.OFF else KOCOM_COMMAND_REV.get(CommandStr.MASTER_LIGHT_ON)
            p_value = '0000000000000000' if cmd == CommandStr.OFF else 'FFFFFFFFFFFFFFFF'
        else:
            if cmd == CommandStr.QUERY:
                p_value = '0000000000000000'
            else:
                if device == Device.ELEVATOR:
                    p_device = KOCOM_DEVICE_REV.get(Device.WALLPAD)
                    p_room = KOCOM_ROOM_REV.get(Device.WALLPAD)
                    p_dst = KOCOM_DEVICE_REV.get(device) + KOCOM_ROOM_REV.get(Device.WALLPAD)
                    p_cmd = KOCOM_COMMAND_REV.get(CommandStr.ON)
                    p_value = '0000000000000000'
                elif device == Device.GAS:
                    p_cmd = KOCOM_COMMAND_REV.get(CommandStr.OFF)
                    p_value = '0000000000000000'
                elif device == Device.LIGHT or device == Device.PLUG:
                    try:
                        all_device = device + str('0')
                        for i in range(1,9):
                            sub_device = device + str(i)
                            if target != sub_device:
                                if target == all_device:
                                    if sub_device in self.wp_list[device][room]:
                                        p_value += 'ff' if value == 'on' else str('00')
                                    else:
                                        p_value += '00'
                                else:
                                    if sub_device in self.wp_list[device][room] and self.wp_list[device][room][sub_device][GeneralString.STATE] == 'on':
                                        p_value += 'ff'
                                    else:
                                        p_value += '00'
                            else:
                                p_value += 'ff' if value == CommandStr.ON else str('00')
                    except:
                        logger.debug('[Make Packet] Error on Device.LIGHT or Device.PLUG')
                elif device == Device.THERMOSTAT:
                    try:
                        mode = self.wp_list[device][room][GeneralString.MODE][GeneralString.SET]
                        target_temp = self.wp_list[device][room][GeneralString.TARGET_TEMP][GeneralString.SET]
                        if mode == GeneralString.HEAT:
                            p_value += '1100'
                        elif mode == DeviceState.SWITCH_OFF:
                            # p_value += '0001'
                            p_value += '0100'
                        else:
                            p_value += '1101'
                        p_value += '{0:02x}'.format(int(float(target_temp)))
                        p_value += '0000000000'
                    except:
                        logger.debug('[Make Packet] Error on Device.THERMOSTAT')
                elif device == Device.FAN:
                    try:
                        mode = self.wp_list[device][room][GeneralString.MODE][GeneralString.SET]
                        speed = self.wp_list[device][room][GeneralString.SPEED][GeneralString.SET]
                        if mode == DeviceState.ON:
                            p_value += '1100'
                        elif mode == DeviceState.OFF:
                            p_value += '0001'
                        p_value += KOCOM_FAN_SPEED_REV.get(speed)
                        p_value += '00000000000'
                    except:
                        logger.debug('[Make Packet] Error on Device.THERMOSTAT')

        if p_value != '':
            packet = p_header + p_device + p_room + p_dst + p_cmd + p_value
            chk_sum = self.check_sum(packet)[1]
            packet += chk_sum + '0d0d'
            return packet
        return False

    def parse_fan(self, value='0000000000000000'):
        fan = {}
        fan[GeneralString.MODE] = DeviceState.ON if value[:2] == '11' else 'off'
        fan[GeneralString.SPEED] = KOCOM_FAN_SPEED.get(value[4:5])
        return fan

    # device = Device.LIGHT(=light),..
    # room = livingroom, ..
    # room 이 MASTER_LIGHT 인 경우에도 여기서 처리될 것이다.
    def parse_switch(self, device, room, value='0000000000000000'):
        switch = {}
        if room == Room.MASTER_LIGHT:
            switch[room] = DeviceState.ON if value is DeviceState.MASTER_LIGHT_ON else DeviceState.MASTER_LIGHT_OFF
        else:
            on_count = 0
            to_i = KOCOM_LIGHT_SIZE.get(room) + 1 if device == Device.LIGHT else KOCOM_PLUG_SIZE.get(room) + 1
            for i in range(1, to_i):
                switch[device + str(i)] = DeviceState.OFF if value[i*2-2:i*2] == '00' else DeviceState.ON
                if value[i*2-2:i*2] != '00':
                    on_count += 1
            switch[device + str('0')] = DeviceState.ON if on_count > 0 else DeviceState.OFF
        return switch

    def parse_thermostat(self, value='0000000000000000', init_temp=False):
        thermo = {}
        heat_mode = GeneralString.HEAT if value[:2] == '11' else DeviceState.OFF
        away_mode = DeviceState.ON if value[2:4] == '01' else DeviceState.OFF
        thermo[GeneralString.CURRENT_TEMP] = int(value[8:10], 16)
        if heat_mode == GeneralString.HEAT and away_mode == DeviceState.ON:
            thermo[GeneralString.MODE] = GeneralString.FAN_ONLY
            thermo[GeneralString.TARGET_TEMP] = INIT_TEMP if not init_temp else int(init_temp)
        elif heat_mode == GeneralString.HEAT and away_mode == DeviceState.OFF:
            thermo[GeneralString.MODE] = GeneralString.HEAT
            thermo[GeneralString.TARGET_TEMP] = int(value[4:6], 16)
        elif heat_mode == DeviceState.OFF:
            thermo[GeneralString.MODE] = DeviceState.OFF
            thermo[GeneralString.TARGET_TEMP] = INIT_TEMP if not init_temp else int(init_temp)
        return thermo

'''
class Grex:
    def __init__(self, client, cont, vent):
        self._name = 'grex'
        self.contoller = cont
        self.ventilator = vent
        self.grex_cont = {GeneralString.MODE: 'off', GeneralString.SPEED: 'off'}
        self.vent_cont = {GeneralString.MODE: 'off', GeneralString.SPEED: 'off'}
        self.mqtt_cont = {GeneralString.MODE: 'off', GeneralString.SPEED: 'off'}

        self.d_mqtt = self.connect_mqtt(client._mqtt, 'GREX')

        _t4 = threading.Thread(target=self.get_serial, args=(self.contoller['serial'], self.contoller['name'], self.contoller['length']))
        _t4.daemon = True
        _t4.start()
        _t5 = threading.Thread(target=self.get_serial, args=(self.ventilator['serial'], self.ventilator['name'], self.ventilator['length']))
        _t5.daemon = True
        _t5.start()

    def connect_mqtt(self, server, name):
        mqtt_client = mqtt.Client()
        mqtt_client.on_message = self.on_message
        #mqtt_client.on_publish = self.on_publish
        mqtt_client.on_subscribe = self.on_subscribe
        mqtt_client.on_connect = self.on_connect

        if server['anonymous'] != BooleanString.TRUE:
            if server['server'] == '' or server['username'] == '' or server['password'] == '':
                logger.info('{} 설정을 확인하세요. Server[{}] ID[{}] PW[{}] Device[{}]'.format(CONF_MQTT, server['server'], server['username'], server['password'], name))
                return False
            mqtt_client.username_pw_set(username=server['username'], password=server['password'])
            logger.debug('{} STATUS. Server[{}] ID[{}] PW[{}] Device[{}]'.format(CONF_MQTT, server['server'], server['username'], server['password'], name))
        else:
            logger.debug('{} STATUS. Server[{}] Device[{}]'.format(CONF_MQTT, server['server'], name))

        mqtt_client.connect(server['server'], 1883, 60)
        mqtt_client.loop_start()
        return mqtt_client

    def on_message(self, client, obj, msg):
        _topic = msg.topic.split('/')
        _payload = msg.payload.decode()

        if 'config' in _topic:
            if _topic[0] == 'rs485' and _topic[3] == 'restart':
                self.homeassistant_device_discovery()
                return
        elif _topic[0] == HAStrings.PREFIX and _topic[1] == HAStrings.FAN and _topic[2] == 'grex':
            logger.info("Message Fan: {} = {}".format(msg.topic, _payload))
            if _topic[3] == GeneralString.SPEED or _topic[3] == GeneralString.MODE:
                if _topic[3] == GeneralString.MODE and self.mqtt_cont[_topic[3]] == 'off' and _payload == 'on' and self.mqtt_cont[GeneralString.SPEED] == 'off':
                    self.mqtt_cont[GeneralString.SPEED] = 'low'
                self.mqtt_cont[_topic[3]] = _payload

                if self.mqtt_cont[GeneralString.MODE] == 'off' and self.mqtt_cont[GeneralString.SPEED] == 'off':
                    self.send_to_homeassistant(HAStrings.FAN, self.mqtt_cont)

    def on_publish(self, client, obj, mid):
        logger.info("Publish: {}".format(str(mid)))

    def on_subscribe(self, client, obj, mid, granted_qos):
        logger.info("Subscribed: {} {}".format(str(mid),str(granted_qos)))

    def on_connect(self, client, userdata, flags, rc):
        if int(rc) == 0:
            logger.info("MQTT connected OK")
            self.homeassistant_device_discovery(initial=True)
        elif int(rc) == 1:
            logger.info("1: Connection refused – incorrect protocol version")
        elif int(rc) == 2:
            logger.info("2: Connection refused – invalid client identifier")
        elif int(rc) == 3:
            logger.info("3: Connection refused – server unavailable")
        elif int(rc) == 4:
            logger.info("4: Connection refused – bad username or password")
        elif int(rc) == 5:
            logger.info("5: Connection refused – not authorised")
        else:
            logger.info(rc, ": Connection refused")

    def homeassistant_device_discovery(self, initial=False):
        subscribe_list = []
        publish_list = []
        subscribe_list.append(('rs485/bridge/#', 0))
        ha_topic = '{}/{}/{}_{}/config'.format(HAStrings.PREFIX, HAStrings.FAN, 'grex', Device.FAN)
        ha_payload = {
            'name': '{}_{}'.format(self._name, Device.FAN),
            'cmd_t': '{}/{}/{}/mode'.format(HAStrings.PREFIX, HAStrings.FAN, 'grex'),
            'stat_t': '{}/{}/{}/state'.format(HAStrings.PREFIX, HAStrings.FAN, 'grex'),
            'spd_cmd_t': '{}/{}/{}/speed'.format(HAStrings.PREFIX, HAStrings.FAN, 'grex'),
            'spd_stat_t': '{}/{}/{}/state'.format(HAStrings.PREFIX, HAStrings.FAN, 'grex'),
            'stat_val_tpl': '{{ value_json.mode }}',
            'spd_val_tpl': '{{ value_json.speed }}',
            'pl_on': 'on',
            'pl_off': 'off',
            'spds': ['low', 'medium', 'high', 'off'],
            'uniq_id': '{}_{}_{}'.format(self._name, 'grex', Device.FAN),
            'device': {
                'name': 'Grex Ventilator',
                'ids': 'grex_ventilator',
                'mf': 'Grex',
                'mdl': 'Ventilator',
                'sw': SW_VERSION
            }
        }
        subscribe_list.append((ha_topic, 0))
        subscribe_list.append((ha_payload['cmd_t'], 0))
        subscribe_list.append((ha_payload['spd_cmd_t'], 0))
        #subscribe_list.append((ha_payload['stat_t'], 0))
        publish_list.append({ha_topic : json.dumps(ha_payload)})

        ha_topic = '{}/{}/{}_{}_mode/config'.format(HAStrings.PREFIX, HAStrings.SENSOR, 'grex', Device.FAN)
        ha_payload = {
            'name': '{}_{}_mode'.format(self._name, Device.FAN),
            'stat_t': '{}/{}/{}_{}/state'.format(HAStrings.PREFIX, HAStrings.SENSOR, 'grex', Device.FAN),
            'val_tpl': '{{ value_json.' + Device.FAN + '_mode }}',
            'ic': 'mdi:play-circle-outline',
            'uniq_id': '{}_{}_{}_mode'.format(self._name, 'grex', Device.FAN),
            'device': {
                'name': 'Grex Ventilator',
                'ids': 'grex_ventilator',
                'mf': 'Grex',
                'mdl': 'Ventilator',
                'sw': SW_VERSION
            }
        }
        subscribe_list.append((ha_topic, 0))
        #subscribe_list.append((ha_payload['stat_t'], 0))
        publish_list.append({ha_topic : json.dumps(ha_payload)})
        ha_topic = '{}/{}/{}_{}_speed/config'.format(HAStrings.PREFIX, HAStrings.SENSOR, 'grex', Device.FAN)
        ha_payload = {
            'name': '{}_{}_speed'.format(self._name, Device.FAN),
            'stat_t': '{}/{}/{}_{}/state'.format(HAStrings.PREFIX, HAStrings.SENSOR, 'grex', Device.FAN),
            'val_tpl': '{{ value_json.' + Device.FAN + '_speed }}',
            'ic': 'mdi:speedometer',
            'uniq_id': '{}_{}_{}_speed'.format(self._name, 'grex', Device.FAN),
            'device': {
                'name': 'Grex Ventilator',
                'ids': 'grex_ventilator',
                'mf': 'Grex',
                'mdl': 'Ventilator',
                'sw': SW_VERSION
            }
        }
        subscribe_list.append((ha_topic, 0))
        #subscribe_list.append((ha_payload['stat_t'], 0))
        publish_list.append({ha_topic : json.dumps(ha_payload)})

        if initial:
            self.d_mqtt.subscribe(subscribe_list)
        for ha in publish_list:
            for topic, payload in ha.items():
                self.d_mqtt.publish(topic, payload)

    def send_to_homeassistant(self, target, value):
        if target == HAStrings.FAN:
            self.d_mqtt.publish("{}/{}/{}/state".format(HAStrings.PREFIX, HAStrings.FAN, 'grex'), json.dumps(value))
            logger.info("[To HA]{}/{}/{}/state = {}".format(HAStrings.PREFIX, HAStrings.FAN, 'grex', json.dumps(value)))
        elif target == HAStrings.SENSOR:
            self.d_mqtt.publish("{}/{}/{}_{}/state".format(HAStrings.PREFIX, HAStrings.SENSOR, 'grex', Device.FAN), json.dumps(value, ensure_ascii = False))
            logger.info("[To HA]{}/{}/{}_{}/state = {}".format(HAStrings.PREFIX, HAStrings.SENSOR, 'grex', Device.FAN, json.dumps(value, ensure_ascii = False)))

    def get_serial(self, ser, packet_name, packet_len):
        buf = []
        start_flag = False
        while True:
            if ser.readable():
                row_data = ser.read()
                hex_d = row_data.hex()
                start_hex = ''
                if packet_name == GeneralString.KOCOM:  start_hex = 'aa'
                elif packet_name == 'grex_ventilator':  start_hex = 'd1'
                elif packet_name == 'grex_controller':  start_hex = 'd0'
                if hex_d == start_hex:
                    start_flag = True
                if start_flag == True:
                    buf.append(hex_d)

                if len(buf) >= packet_len:
                    joindata = ''.join(buf)
                    chksum = self.validate_checksum(joindata, packet_len - 1)
                    #logger.debug("[From {}]{} {} {}".format(packet_name, joindata, str(chksum[0]), str(chksum[1])))
                    if chksum[0]:
                        self.packet_parsing(joindata, packet_name)
                    buf = []
                    start_flag = False

    def packet_parsing(self, packet, packet_name):
        p_prefix = packet[:4]

        if p_prefix == 'd00a':
            m_packet = self.make_response_packet(0)
            m_chksum = self.validate_checksum(m_packet, 11)
            if m_chksum[0]:
                self.contoller['serial'].write(bytearray.fromhex(m_packet))
            logger.debug('[From Grex]error code : E1')
        elif p_prefix == 'd08a':
            control_packet = ''
            response_packet = ''
            p_mode = packet[8:12]
            p_speed = packet[12:16]

            if self.grex_cont[GeneralString.MODE] != GREX_MODE[p_mode] or self.grex_cont[GeneralString.SPEED] != GREX_SPEED[p_speed]:
                self.grex_cont[GeneralString.MODE] = GREX_MODE[p_mode]
                self.grex_cont[GeneralString.SPEED] = GREX_SPEED[p_speed]
                logger.info('[From {}]mode:{} / speed:{}'.format(packet_name, self.grex_cont[GeneralString.MODE], self.grex_cont[GeneralString.SPEED]))
                send_to_HAStrings.FAN = {GeneralString.MODE: 'off', GeneralString.SPEED: 'off'}
                if self.grex_cont[GeneralString.MODE] != 'off' or (self.grex_cont[GeneralString.MODE] == 'off' and self.mqtt_cont[GeneralString.MODE] == 'on'):
                    send_to_HAStrings.FAN[GeneralString.MODE] = 'on'
                    send_to_HAStrings.FAN[GeneralString.SPEED] = self.grex_cont[GeneralString.SPEED]
                self.send_to_homeassistant(HAStrings.FAN, send_to_HAStrings.FAN)

                send_to_HAStrings.SENSOR = {'fan_mode': 'off', 'fan_speed': 'off'}
                if self.grex_cont[GeneralString.MODE] != 'off' or (self.grex_cont[GeneralString.MODE] == 'off' and self.mqtt_cont[GeneralString.MODE] == 'on'):
                    if self.grex_cont[GeneralString.MODE] == 'auto':
                        send_to_HAStrings.SENSOR['fan_mode'] = '자동'
                    elif self.grex_cont[GeneralString.MODE] == 'manual':
                        send_to_HAStrings.SENSOR['fan_mode'] = '수동'
                    elif self.grex_cont[GeneralString.MODE] == 'sleep':
                        send_to_HAStrings.SENSOR['fan_mode'] = '취침'
                    elif self.grex_cont[GeneralString.MODE] == 'off' and self.mqtt_cont[GeneralString.MODE] == 'on':
                        send_to_HAStrings.SENSOR['fan_mode'] = 'HA'
                    if self.grex_cont[GeneralString.SPEED] == 'low':
                        send_to_HAStrings.SENSOR['fan_speed'] = '1단'
                    elif self.grex_cont[GeneralString.SPEED] == 'medium':
                        send_to_HAStrings.SENSOR['fan_speed'] = '2단'
                    elif self.grex_cont[GeneralString.SPEED] == 'high':
                        send_to_HAStrings.SENSOR['fan_speed'] = '3단'
                    elif self.grex_cont[GeneralString.SPEED] == 'off':
                        send_to_HAStrings.SENSOR['fan_speed'] = '대기'
                self.send_to_homeassistant(HAStrings.SENSOR, send_to_HAStrings.SENSOR)

            if self.grex_cont[GeneralString.MODE] == 'off':
                response_packet = self.make_response_packet(0)
                if self.mqtt_cont[GeneralString.MODE] == 'off' or (self.mqtt_cont[GeneralString.MODE] == 'on' and self.mqtt_cont[GeneralString.SPEED] == 'off'):
                    control_packet = self.make_control_packet('off', 'off')
                elif self.mqtt_cont[GeneralString.MODE] == 'on' and self.mqtt_cont[GeneralString.SPEED] != 'off':
                    control_packet = self.make_control_packet('manual', self.mqtt_cont[GeneralString.SPEED])
            else:
                control_packet = self.make_control_packet(self.grex_cont[GeneralString.MODE], self.grex_cont[GeneralString.SPEED])
                if self.grex_cont[GeneralString.SPEED] == 'low':
                    response_packet = self.make_response_packet(1)
                elif self.grex_cont[GeneralString.SPEED] == 'medium':
                    response_packet = self.make_response_packet(2)
                elif self.grex_cont[GeneralString.SPEED] == 'high':
                    response_packet = self.make_response_packet(3)
                elif self.grex_cont[GeneralString.SPEED] == 'off':
                    response_packet = self.make_response_packet(0)

            if response_packet != '':
                self.contoller['serial'].write(bytearray.fromhex(response_packet))
                #logger.debug("[Tooo grex_controller]{}".format(response_packet))
            if control_packet != '':
                self.ventilator['serial'].write(bytearray.fromhex(control_packet))
                #logger.debug("[Tooo grex_ventilator]{}".format(control_packet))

        elif p_prefix == 'd18b':
            p_speed = packet[8:12]
            if self.vent_cont[GeneralString.SPEED] != GREX_SPEED[p_speed]:
                self.vent_cont[GeneralString.SPEED] = GREX_SPEED[p_speed]
                logger.info('[From {}]speed:{}'.format(packet_name, self.vent_cont[GeneralString.SPEED]))

                send_to_HAStrings.FAN = {GeneralString.MODE: 'off', GeneralString.SPEED: 'off'}
                if self.grex_cont[GeneralString.MODE] != 'off' or (self.grex_cont[GeneralString.MODE] == 'off' and self.mqtt_cont[GeneralString.MODE] == 'on'):
                    send_to_HAStrings.FAN[GeneralString.MODE] = 'on'
                    send_to_HAStrings.FAN[GeneralString.SPEED] = self.vent_cont[GeneralString.SPEED]
                self.send_to_homeassistant(HAStrings.FAN, send_to_HAStrings.FAN)

                send_to_HAStrings.SENSOR = {'fan_mode': 'off', 'fan_speed': 'off'}
                if self.grex_cont[GeneralString.MODE] != 'off' or (self.grex_cont[GeneralString.MODE] == 'off' and self.mqtt_cont[GeneralString.MODE] == 'on'):
                    if self.grex_cont[GeneralString.MODE] == 'auto':
                        send_to_HAStrings.SENSOR['fan_mode'] = '자동'
                    elif self.grex_cont[GeneralString.MODE] == 'manual':
                        send_to_HAStrings.SENSOR['fan_mode'] = '수동'
                    elif self.grex_cont[GeneralString.MODE] == 'sleep':
                        send_to_HAStrings.SENSOR['fan_mode'] = '취침'
                    elif self.grex_cont[GeneralString.MODE] == 'off' and self.mqtt_cont[GeneralString.MODE] == 'on':
                        send_to_HAStrings.SENSOR['fan_mode'] = 'HA'
                    if self.vent_cont[GeneralString.SPEED] == 'low':
                        send_to_HAStrings.SENSOR['fan_speed'] = '1단'
                    elif self.vent_cont[GeneralString.SPEED] == 'medium':
                        send_to_HAStrings.SENSOR['fan_speed'] = '2단'
                    elif self.vent_cont[GeneralString.SPEED] == 'high':
                        send_to_HAStrings.SENSOR['fan_speed'] = '3단'
                    elif self.vent_cont[GeneralString.SPEED] == 'off':
                        send_to_HAStrings.SENSOR['fan_speed'] = '대기'
                self.send_to_homeassistant(HAStrings.SENSOR, send_to_HAStrings.SENSOR)

    def make_control_packet(self, mode, speed):
        prefix = 'd08ae022'
        if mode == 'off':
            packet_mode = '0000'
        elif mode == 'auto':
            packet_mode = '0100'
        elif mode == 'manual':
            packet_mode = '0200'
        elif mode == 'sleep':
            packet_mode = '0300'
        else:
            return ''
        if speed == 'off':
            packet_speed = '0000'
        elif speed == 'low':
            packet_speed = '0101'
        elif speed == 'medium':
            packet_speed = '0202'
        elif speed == 'high':
            packet_speed = '0303'
        else:
            return ''
        if ((mode == 'auto' or mode == 'sleep') and (speed == 'off')) or (speed == 'low' or speed == 'medium' or speed == 'high'):
            postfix = '0001'
        else:
            postfix = '0000'

        packet = prefix + packet_mode + packet_speed + postfix
        packet_checksum = self.make_checksum(packet, 10)
        packet = packet + packet_checksum
        return packet

    def make_response_packet(self, speed):
        prefix = 'd18be021'
        if speed == 0:
            packet_speed = '0000'
        elif speed == 1:
            packet_speed = '0101'
        elif speed == 2:
            packet_speed = '0202'
        elif speed == 3:
            packet_speed = '0303'
        if speed == 0:
            postfix = '0000000000'
        elif speed > 0:
            postfix = '0000000100'

        packet = prefix + packet_speed + postfix
        packet_checksum = self.make_checksum(packet, 11)
        packet = packet + packet_checksum
        return packet

    def hex_to_list(self, hex_string):
        slide_windows = 2
        start = 0
        buf = []
        for x in range(int(len(hex_string) / 2)):
            buf.append('0x{}'.format(hex_string[start: slide_windows].lower()))
            slide_windows += 2
            start += 2
        return buf

    def validate_checksum(self, packet, length):
        hex_list = self.hex_to_list(packet)
        sum_buf = 0
        for ix, x in enumerate(hex_list):
            if ix > 0:
                hex_int = int(x, 16)
                if ix == length:
                    chksum_hex = '0x{0:02x}'.format((sum_buf % 256))
                    if hex_list[ix] == chksum_hex:
                        return (True, hex_list[ix])
                    else:
                        return (False, hex_list[ix])
                sum_buf += hex_int

    def make_checksum(self, packet, length):
        hex_list = self.hex_to_list(packet)
        sum_buf = 0
        chksum_hex = 0
        for ix, x in enumerate(hex_list):
            if ix > 0:
                hex_int = int(x, 16)
                sum_buf += hex_int
                if ix == length - 1:
                    chksum_hex = '{0:02x}'.format((sum_buf % 256))
        return str(chksum_hex)
'''

if __name__ == '__main__':
    #logger 인스턴스 생성 및 로그레벨 설정
    logger = logging.getLogger(CONF_LOGNAME)
    logger.setLevel(logging.INFO)
    if CONF_LOGLEVEL == "info": logger.setLevel(logging.INFO)
    if CONF_LOGLEVEL == "debug": logger.setLevel(logging.DEBUG)
    if CONF_LOGLEVEL == "warn": logger.setLevel(logging.WARN)

    # formatter 생성
    logFormatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s : Line %(lineno)s - %(message)s')

    # fileHandler, StreamHandler 생성
    file_max_bytes = 100 * 1024 * 10 # 1 MB 사이즈
    logFileHandler = logging.handlers.RotatingFileHandler(filename=log_path, maxBytes=file_max_bytes, backupCount=10, encoding='utf-8')
    logStreamHandler = logging.StreamHandler()

    # handler 에 formatter 설정
    logFileHandler.setFormatter(logFormatter)
    logStreamHandler.setFormatter(logFormatter)
    logFileHandler.suffix = "%Y%m%d"

    logger.addHandler(logFileHandler)
    #logger.addHandler(logStreamHandler)

    logging.info('{} 시작'.format(SW_VERSION))
    logger.info('{} 시작'.format(SW_VERSION))

    if DEFAULT_SPEED not in ['low', 'medium', 'high']:
        logger.info('[Error] DEFAULT_SPEED 설정오류로 medium 으로 설정. {} -> medium'.format(DEFAULT_SPEED))
        DEFAULT_SPEED = 'medium'

    _grex_ventilator = False
    _grex_controller = False
    connection_flag = False
    while not connection_flag:
        r = rs485()
        connection_flag = True
        if r._type == 'serial':
            for device in r._device:
                if r._connect[device].isOpen():
                    _name = r._device[device]
                    try:
                        logger.info('[CONFIG] {} 초기화'.format(_name))
                        if _name == GeneralString.KOCOM:
                            kocom = Kocom(r, _name, device, 42)
                        elif _name == 'grex_ventilator':
                            _grex_ventilator = {'serial': r._connect[device], 'name': _name, 'length': 12}
                        elif _name == 'grex_controller':
                            _grex_controller = {'serial': r._connect[device], 'name': _name, 'length': 11}
                    except:
                        logger.info('[CONFIG] {} 초기화 실패'.format(_name))
        elif r._type == 'socket':
            _name = r._device
            if _name == GeneralString.KOCOM:
                kocom = Kocom(r, _name, _name, 42)
                if not kocom.connection_lost():
                    logger.info('[ERROR] 서버 연결이 끊어져 1분 후 재접속을 시도합니다.')
                    time.sleep(60)
                    connection_flag = False
        if _grex_ventilator is not False and _grex_controller is not False:
            _grex = Grex(r, _grex_controller, _grex_ventilator)
