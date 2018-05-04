# Domoticz TP-Link Wi-Fi Smart Plug plugin
#
# Plugin based on reverse engineering of the TP-Link HS110, courtesy of Lubomir Stroetmann and Tobias Esser.
# https://www.softscheck.com/en/reverse-engineering-tp-link-hs110/
#
# Author: Dan Hallgren
#
"""
<plugin key="tplinksmartplug" name="TP-Link Wi-Fi Smart Plug HS100/HS110" version="0.1.0">
    <description>
        <h2>TP-Link Wi-Fi Smart Plug</h2>
        <ul style="list-sytel-type:square">
            <li>on/off switching</li>
            <li>emeter realtime power (HS110)</li>
            <li>emeter realtime current (HS110)</li>
            <li>emeter realtime voltage (HS110)</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>switch - On/Off</li>
            <li>power - Realtime power in Watts</li>
            <li>current - Realtime current in ampere</li>
            <li>voltage - Voltage input</li>
        </ul>
    </description>
    <params>
        <param field="Address" label="IP Address" width="200px" required="true"/>
        <param field="Mode1" label="Model" width="150px" required="false">
             <options>
                <option label="HS100" value="HS100" default="true"/>
                <option label="HS110" value="HS110"  default="false" />
            </options>
        </param>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
    </params>
</plugin>
"""
import json
import socket

import Domoticz

PORT = 9999
STATES = ('off', 'on', 'unknown')


class TpLinkSmartPlugPlugin:
    enabled = False
    connection = None

    def __init__(self):
        self.interval = 6  # 6*10 seconds
        self.heartbeatcounter = 0

    def onStart(self):
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)
            DumpConfigToLog()

        if len(Devices) == 0:
            Domoticz.Device(Name="switch", Unit=1, TypeName="Switch", Used=1).Create()
            Domoticz.Log("Tp-Link smart plug device created")

        if Parameters["Mode1"] == "HS110" and len(Devices) <= 1:
            # Create more devices here
            Domoticz.Device(Name="emeter current (A)", Unit=2, Type=243, Subtype=23).Create()
            Domoticz.Device(Name="emeter voltage (V)", Unit=3, Type=243, Subtype=8).Create()
            Domoticz.Device(Name="emeter power (W)", Unit=4, Type=243, Subtype=31, Image=1, Used=1).Create()

        state = self.get_switch_state()
        if state in 'off':
            Devices[1].Update(0, '0')
        elif state in 'on':
            Devices[1].Update(1, '100')
        else:
            Devices[1].Update(1, '50')

    def onStop(self):
        # Domoticz.Log("onStop called")
        pass

    def onConnect(self, Connection, Status, Description):
        # Domoticz.Log("onConnect called")
        pass

    def onMessage(self, Connection, Data, Status, Extra):
        # Domoticz.Log("onMessage called")
        pass

    def onCommand(self, unit, command, level, hue):
        Domoticz.Log("onCommand called for Unit " +
                     str(unit) + ": Parameter '" + str(command) + "', Level: " + str(level))

        if command.lower() == 'on':
            cmd = {
                "system": {
                    "set_relay_state": {"state": 1}
                }
            }
            state = (1, '100')

        elif command.lower() == 'off':
            cmd = {
                "system": {
                    "set_relay_state": {"state": 0}
                }
            }
            state = (0, '0')

        result = self._send_json_cmd(json.dumps(cmd))
        Domoticz.Debug("got response: {}".format(result))

        err_code = result.get('system', {}).get('set_relay_state', {}).get('err_code', 1)

        if err_code == 0:
            Devices[1].Update(*state)

        # Reset counter so we trigger emeter poll next heartbeat
        self.heartbeatcounter = 0

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status +
                     "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        # Domoticz.Log("onDisconnect called")
        pass

    def onHeartbeat(self):
        if self.heartbeatcounter % self.interval == 0:
            self.update_emeter_values()

        self.heartbeatcounter += 1

    def _encrypt(self, data):
        key = 171
        result = b"\x00\x00\x00" + chr(len(data)).encode('latin-1')
        for i in data.encode('latin-1'):
            a = key ^ i
            key = a
            result += bytes([a])
        return result

    def _decrypt(self, data):
        key = 171
        result = ""
        for i in data:
            a = key ^ i
            key = i
            result += bytes([a]).decode('latin-1')
        return result

    def _send_json_cmd(self, cmd):
        ret = {}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            sock.connect((Parameters["Address"], PORT))
            data = self._encrypt(cmd)
            sock.send(data)
            data = sock.recv(1024)
            Domoticz.Debug('data len: {}'.format(len(data)))
            sock.close()
        except socket.error as e:
            Domoticz.Log('send command error: {}'.format(str(e)))
            raise

        try:
            json_resp = self._decrypt(data[4:])
            ret = json.loads(json_resp)
        except (TypeError, JSONDecodeError) as e:
            Domoticz.Log('decode error: {}'.format(str(e)))
            Domoticz.Log('data: {}'.format(str(data)))
            raise

        return ret

    def update_emeter_values(self):
        if Parameters["Mode1"] == "HS110":
            cmd = {
                "emeter": {
                    "get_realtime": {}
                }
            }

            result = self._send_json_cmd(json.dumps(cmd))
            Domoticz.Debug("got response: {}".format(result))

            realtime_result = result.get('emeter', {}).get('get_realtime', {})
            err_code = realtime_result.get('err_code', 1)

            if err_code == 0:
                Devices[2].Update(nValue=int(1 * realtime_result['current']), sValue=str(realtime_result['current']))
                Devices[3].Update(nValue=int(1 * realtime_result['voltage']), sValue=str(realtime_result['voltage']))
                Devices[4].Update(nValue=int(1 * realtime_result['power']), sValue=str(realtime_result['power']))

    def get_switch_state(self):
        cmd = {
            "system": {
                "get_sysinfo": "null"
            }
        }
        result = self._send_json_cmd(json.dumps(cmd))
        print(result)

        err_code = result.get('system', {}).get('get_sysinfo', {}).get('err_code', 1)

        if err_code == 0:
            state = result['system']['get_sysinfo']['relay_state']
        else:
            state = 2

        return STATES[state]


global _plugin
_plugin = TpLinkSmartPlugPlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)


def onMessage(Connection, Data, Status, Extra):
    global _plugin
    _plugin.onMessage(Connection, Data, Status, Extra)


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)


def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)


def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return
