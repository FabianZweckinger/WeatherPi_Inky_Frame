from datetime import datetime
from fritzconnection import FritzConnection
import requests
import xml.etree.ElementTree as Et

# Fritzbox API config
FRITZBOX_IP = '192.168.178.1'
FRITZBOX_PASSWORD = 'XXXXXXXXX'


# Definition of call's type value:
# src: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf
# 1 incoming Call answered by phone or answering machine.
# 2 missed Incoming call was not answered by internal phone or answering machine.
# 3 outgoing Finished call to external number.
# 9 active incoming Phone or answering machine has answered the incoming call and the call isn’t over yet.
# 10 rejected incoming The incoming call was refused e.g. by call barring.
# 11 active outgoing Call to external number isn’t over yet.
# callType = {
#    1: 'CALL_ANSWERED',
#    2: 'CALL_MISSED',
#    3: 'CALL_OUTGOING_FINISHED',
#    9: 'CALL_INCOMING_ACTIVE',
#    10: 'CALL_REFUSED',
#    11: 'CALL_OUTGOING_ACTIVE'
# }

def get_calls(current_datetime, call_amount):
    # Connect to FritzBox
    fc = FritzConnection(address=FRITZBOX_IP, password=FRITZBOX_PASSWORD)
    fc.reconnect()

    # Get URL to the call list with session id
    state = fc.call_action('X_AVM-DE_OnTel', 'GetCallList')
    calls_url = state.get('NewCallListURL')
    print('Fritzbox API URL: ' + calls_url)

    # Parse xml content
    xml_content = requests.get(calls_url).content
    xml_content = Et.ElementTree(Et.fromstring(xml_content)).getroot()

    # Extract data:
    # <Call>
    #   <Id>123</Id>
    #   <Type>2</Type>
    #   <Caller>01234567890</Caller>
    #   <Called>SIP: 01234567891</Called>
    #   <CalledNumber>01234567891</CalledNumber>
    #   <Name></Name>
    #   <Numbertype>sip</Numbertype>
    #   <Device></Device>
    #   <Port>-1</Port>
    #   <Date>01.01.22 12:00</Date>
    #   <Duration>0:30</Duration>   (h:mm format)
    #   <Count></Count>
    #   <Path />
    # </Call>

    # Get date and time:
    #current_datetime_json = [current_datetime.strftime('%A')[:2],
    #                         current_datetime.minute,
    #                         current_datetime.hour,
    #                         current_datetime.day,
    #                         current_datetime.month,
    #                         current_datetime.year]

    calls_state = []
    calls_number = []
    calls_day = []
    calls_month = []
    calls_year = []
    calls_hour = []
    calls_minute = []

    # Loop over CALL_BACKLOG amount calls, skipping the first timestamp element
    for call in xml_content[1:(call_amount + 1)]:
        call_datetime = datetime.strptime(call[9].text, '%d.%m.%y %H:%M')
        calls_state.append(int(call[1].text))
        calls_number.append(call[2].text)
        calls_day.append(call_datetime.day)
        calls_month.append(call_datetime.month)
        calls_year.append(call_datetime.year)
        calls_hour.append(call_datetime.hour)
        calls_minute.append(call_datetime.minute)

    return {
        'calls_state': calls_state,
        'calls_number': calls_number,
        'calls_day':  calls_day,
        'calls_month':  calls_month,
        'calls_year':  calls_year,
        'calls_hour':  calls_hour,
        'calls_minute':  calls_minute
    }
