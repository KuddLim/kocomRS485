import os
import json

from rs485 import rs485, Kocom

option_file = './test_config.json'

INIT_TEMP = -1
SCAN_INTERVAL = 0
SCANNING_INTERVAL = 0
DEFAULT_SPEED = 0
CONF_LOGLEVEL = 'info'

if os.path.isfile(option_file):
    with open(option_file) as json_file:
        json_data = json.load(json_file)
        INIT_TEMP = json_data['Advanced']['INIT_TEMP']
        SCAN_INTERVAL = json_data['Advanced']['SCAN_INTERVAL']
        SCANNING_INTERVAL = json_data['Advanced']['SCANNING_INTERVAL']
        DEFAULT_SPEED = json_data['Advanced']['DEFAULT_SPEED']
        CONF_LOGLEVEL = json_data['Advanced']['LOGLEVEL']
        KOCOM_LIGHT_SIZE = {}
        dict_data = json_data['KOCOM_LIGHT_SIZE']
        for i in dict_data:
            KOCOM_LIGHT_SIZE[i['name']] = i['number']
        KOCOM_PLUG_SIZE = {}
        dict_data = json_data['KOCOM_PLUG_SIZE']
        for i in dict_data:
            KOCOM_PLUG_SIZE[i['name']] = i['number']
        num = 0
        KOCOM_ROOM = {}
        list_data = json_data['KOCOM_ROOM']
        for i in list_data:
            if num < 10:
                num_key = "0%d" % (num)
            else:
                num_key = "%d" % (num)
            KOCOM_ROOM[num_key] = i
            num += 1
        num = 0
        KOCOM_ROOM_THERMOSTAT = {}
        list_data = json_data['KOCOM_ROOM_THERMOSTAT']
        for i in list_data:
            if num < 10:
                num_key = "0%d" % (num)
            else:
                num_key = "%d" % (num)
            KOCOM_ROOM_THERMOSTAT[num_key] = i
            num += 1