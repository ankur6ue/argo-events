import json
import base64
import argparse
import logging
from mysql.connector import connect, Error
from datetime import datetime
from pytz import timezone
import time
import os

# This program is used to produce a docker image which is used in a kubernetes job triggered by the SQS sensor.
# The event info is passed as the command argument. The program parses the event info, opens a connection to
# a mysql service and creates a new db record, including the current time stamp.


def main():

    parser = argparse.ArgumentParser(description='program parameters')
    parser.add_argument('--msg', dest='msg', type=str, help='message content')
    args = parser.parse_args()
    created_ts = time.time()

    # logging config
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console = logging.StreamHandler()
    # to also write logs to file:
    # fh = logging.FileHandler('tmp/spam.log')
    console.setFormatter(formatter)
    # add the handler to the root logger
    logger = logging.getLogger('sqs-trigger-app')
    # setting up log level must be like this, otherwise it doesn't work or leads to duplicate logs
    logger.setLevel(logging.INFO)
    logger.addHandler(console)

    # printing initial json
    msg_json = json.loads(args.msg)
    event_id = msg_json['context']['id']
    # don't use this timestamp, because this is added by sqs event source and is not the original message timestamp
    # event_ts = msg_json['context']['time']
    # event_ts = datetime.strptime(event_ts, "%Y-%m-%dT%H:%M:%SZ")
    msg_data_decoded = json.loads(base64.b64decode(msg_json['data']).decode('utf-8'))
    if os.getenv("DEBUG_MODE") == "1":
        logger.info("original message: {0}".format(args.msg))
        logger.info("message data decoded: {0}".format(msg_data_decoded))

    # print("body.payload: {0}".format(msg_data_decoded["body"]["payload"]))

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
            now_time = datetime.now(timezone('US/Eastern'))
            created_at_ts = now_time.strftime(fmt)
            payload_id = msg_data_decoded["body"]["id"]
            author = msg_data_decoded["body"]["author"]
            custom_message = msg_data_decoded["body"]["message"]
            event_ts = msg_data_decoded["messageAttributes"]["Timestamp"]["StringValue"]
            x.execute("""INSERT into argo_event_record (PayloadId, CustomMessage, EventType, Author, EventTimestamp, CreatedAtTimestamp) \
             values(%s ,%s, %s, %s, %s, %s)""", (payload_id, custom_message, 'sqs', author, event_ts, created_at_ts))
            connection.commit()

    except Error as e:
        logger.error("failed connecting to database")
        logger.error(e)


if __name__ == '__main__':
    main()