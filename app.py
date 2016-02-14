import os
import time
from urllib import urlopen
from xml.etree.ElementTree import ElementTree
from google.protobuf import text_format

from flask import Flask
from flask import request
import iso8601
from calendar import timegm

import gtfs_realtime_pb2

poikkeusURL = 'http://www.poikkeusinfo.fi/xml/v3'
agency_id = 'HSL'

tree = ElementTree()

app = Flask(__name__)


@app.route('/')
def index():
    return get_disruptions()

def get_disruptions():
    """Get alerts from HSL XML interface and format them into GTFS-RT"""
    tree.parse(urlopen(poikkeusURL))
    msg = init_feed_message()
    disruptions = tree.getroot()
    if (disruptions is not None):
        populate_feed_message(disruptions, msg)

    if 'debug' in request.args:
        return text_format.MessageToString(msg)
    else:
        return msg.SerializeToString()

def populate_feed_message(disruptions, msg):
    msg.header.timestamp = int(timegm(
        iso8601.parse_date(disruptions.attrib['time']).utctimetuple()))
    for disruption in list(disruptions):
        if (disruption.tag == 'DISRUPTION'):
            alert_entity = init_alert_entity(msg, disruption)
            if alert_entity.alert.effect == 1:
                trip_update_entity = init_trip_update_entity(msg, disruption)
            else:
                trip_update_entity = None
            for line in list(disruption.find('TARGETS')):
                inf = init_informed_entity(alert_entity)
                if 'route_type' in line.attrib and line.attrib['route_type']:
                    inf.route_type = int(line.attrib['route_type'])
                if 'id' in line.attrib and line.attrib['id']:
                    if 'direction' in line.attrib and line.attrib['direction']:
                        direction = int(line.attrib['direction'])-1
                    else:
                        direction = None
                    set_id_and_direction(line.attrib['id'], inf, trip_update_entity, direction)
                if 'deptime' in line.attrib and line.attrib['deptime']:
                    set_start_time_to_informed_and_trip_update_entities(iso8601.parse_date(line.attrib['deptime']), inf, trip_update_entity)

            set_is_deleted(disruption, alert_entity, trip_update_entity)
            set_active_period_to_alert_entity(disruption, alert_entity)
            set_description_to_alert_entity(disruption, alert_entity)


def init_feed_message():
    msg = gtfs_realtime_pb2.FeedMessage()
    msg.header.gtfs_realtime_version = "1.0"
    msg.header.incrementality = msg.header.FULL_DATASET
    return msg

def set_description_to_alert_entity(disruption, alert_entity):
    texts = list(disruption.find('INFO'))
    for t in texts:
        if t.text and t.attrib['lang']:
            head = alert_entity.alert.description_text.translation.add()
            head.language = t.attrib['lang']
            head.text = t.text

def set_active_period_to_alert_entity(disruption, alert_entity):
    v = disruption.find('VALIDITY')
    vper = alert_entity.alert.active_period.add()
    vper.start = int(timegm(iso8601.parse_date(v.attrib['from']).utctimetuple()))
    vper.end = int(timegm(iso8601.parse_date(v.attrib['to']).utctimetuple()))

def set_is_deleted(disruption, alert_entity, trip_update_entity=None):
    v = disruption.find('VALIDITY')
    alert_entity.is_deleted = (v.attrib['status'] == "0")
    if trip_update_entity is not None:
        trip_update_entity.is_deleted = (v.attrib['status'] == "0")

def init_trip_update_entity(feed_message, disruption):
    trip_update_entity = feed_message.entity.add()
    trip_update_entity.id = "trip_update:" + disruption.attrib['id']
    trip_update_entity.trip_update.trip.schedule_relationship = trip_update_entity.trip_update.trip.CANCELED
    return trip_update_entity

def init_alert_entity(feed_message, disruption):
    alert_entity = feed_message.entity.add()
    alert_entity.id = disruption.attrib['id']
    alert_entity.alert.effect = int(disruption.attrib['effect'])
    return alert_entity

def init_informed_entity(alert_entity):
    informed_entity = alert_entity.alert.informed_entity.add()
    informed_entity.agency_id = agency_id
    return informed_entity

def set_start_time(start_time, trip):
    trip.start_date = start_time.strftime("%Y%m%d")
    trip.start_time = start_time.strftime("%H:%M:%S")

def set_start_time_to_informed_and_trip_update_entities(start_time,
                                                        informed_entity,
                                                        trip_update_entity=None):
    set_start_time(start_time, informed_entity.trip)
    if trip_update_entity is not None:
        set_start_time(start_time, trip_update_entity.trip_update.trip)

def set_id_and_direction(id, informed_entity, trip_update_entity=None, direction=None):
    informed_entity.route_id = id
    informed_entity.trip.route_id = id
    if trip_update_entity is not None:
        trip_update_entity.trip_update.trip.route_id = id
    if direction is not None:
        informed_entity.trip.direction_id = direction
        if trip_update_entity is not None:
            trip_update_entity.trip_update.trip.direction_id = direction


def main(debug=False):
    port = int(os.environ.get('PORT', 5000))
    app.debug = debug
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()
