from typing import Union
import time
from fastapi import Request, FastAPI
from pydantic import BaseModel
from mysql.connector import connect, Error
import json
import base64
import logging
from datetime import datetime
from pytz import timezone

# This program exposes a POST endpoint at /event that is used by the SNS trigger to post info about a SNS event that
# has passed the source/sensor filter stage, in the request body. The endpoint parses the event info and creates
# a new db record, including the current time stamp.


# This is not used right now..
class SNSEvent(BaseModel):
    PayloadId: int
    EventType: str
    Author: str
    EventTimestamp: str
    CustomMessage: Union[str, None] = None
    created_ts = time.time()
    CreatedAtTimestamp = datetime.fromtimestamp(created_ts).strftime('%Y-%m-%d %H:%M:%S')


app = FastAPI()

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console = logging.StreamHandler()
# to also write logs to file:
# fh = logging.FileHandler('tmp/spam.log')
console.setFormatter(formatter)
# add the handler to the root logger
logger = logging.getLogger('sns-trigger-app')
# setting up log level must be like this, otherwise it doesn't work or leads to duplicate logs
logger.setLevel(logging.INFO)
logger.addHandler(console)


@app.post("/event/")
async def create_db_entry(request: Request):

    msg_body = await request.body()
    msg_json = json.loads(msg_body)
    msg_json = json.loads(msg_json['data'])

    # This info is added by the event source. We can use the event_type to infer the type of event
    event_id = msg_json['context']['id']
    event_type = msg_json['context']['type']

    msg_data_decoded = json.loads(base64.b64decode(msg_json['data']).decode('utf-8'))
    if msg_data_decoded["debug_mode"] == 1:
        logger.info("original request body: {0}".format(msg_body))
        logger.info("message data decoded: {0}".format(msg_data_decoded))
    # don't use this time, this is the timestamp inserted by argo sensor. We are interested in the original Timestamp
    # in the message
    # event_ts = msg_json['context']['time']

    # connect to the mysql database and insert a record of the following schema:
    # PayloadId, EventType, CustomMessage, Author, EventTimestamp, CreatedAtTimestamp

    try:
        with connect(
                host="mysql.argo-events",
                password="password",
                database="argo_event_record_db"
        ) as connection:
            logger.info("successfully connected to database")
            x = connection.cursor()
            # need to be careful of timezone, otherwise the actual time will depend on the timezone of the EC2 instance
            # where this code is running!
            fmt = '%Y-%m-%d %H:%M:%S.%f'
            est = timezone('US/Eastern')
            now_time = datetime.now(est)
            created_at_ts = now_time.strftime(fmt)
            # logger.info(msg_data_decoded["body"]["Message"])
            payload_id = msg_data_decoded["id"]
            author = msg_data_decoded["author"]
            custom_message = msg_data_decoded["message"]
            event_ts = msg_data_decoded["Timestamp"] # in UTC, convert to US/East
            event_ts = datetime.strptime(event_ts, "%Y-%m-%dT%H:%M:%S.%fZ")
            # converting to EST, so it can be compared with now time, also in EST
            event_ts = event_ts.astimezone(est)
            x.execute("""INSERT into argo_event_record (PayloadId, EventType, Author, CustomMessage, EventTimestamp, CreatedAtTimestamp) \
             values(%s ,%s, %s, %s, %s, %s)""", (payload_id, event_type, author, custom_message, \
                                             event_ts, created_at_ts))
            connection.commit()

    except Error as e:
        logger.error("failed connecting to database")

    return await request.json()

# Test:curl -X POST "http://127.0.0.1:8000/event/" -H "Content-Type: application/json" -d '{"Author": "Ankur", "PayloadId": 4, "EventType": "sqs", "CustomMessage": "tbd", "EventTimestamp": "2007-03-04T21:08:12Z"}'
# on kubernetes
# kubectl run mycurlpod --image=curlimages/curl -i --tty -- sh
# if pod is already running:
# kubectl exec mycurlpod -i --tty -- sh
# curl -X POST "http://http-server-svc.argo-events:8000/event/" -H "Content-Type: application/json" -d '{"Author": "Ankur", "PayloadId": 4, "EventType": "sqs", "CustomMessage": "tbd", "EventTimestamp": "2007-03-04T21:08:12Z"}'
