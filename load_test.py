import datetime
import boto3
import os
from dotenv import dotenv_values, load_dotenv
import configparser
import time
import random
import kubernetes
from kubernetes import client, config


'''
This program is used to run load test for SNS/SQS argo event sources, sensors and triggers. The program does the 
following:
1. Load configuration k-v pairs from load_test_config.env. These k-v pairs include AWS creds, profile name, 
SNS topic and SQS queue we'll be sending notifications, messages
2. Create a list of JSON formatted message strings where the author and id keys are sampled from a list of authors and
ids
3. Run through this list and send each message to the SNS topic and SQS queue. The duration between each message
is randomly sampled between 0 - 3000ms. 
4. Every 50 messages, use the kubernetes-python API to delete completed jobs (created by the SQS trigger). This is done
to avoid having too many completed jobs on the cluster, which can result in out-of-pods error.   
'''

# This is the prefix for the jobs created by the SQS trigger
JOB_NAME = "hello-world"
# This is the namespace where the SQS trigger jobs are created.
NAMESPACE = "argo-events-test"


def update_job(api_instance, job):
    # Update container image
    job.spec.template.spec.containers[0].image = "perl"
    api_response = api_instance.patch_namespaced_job(
        name=JOB_NAME,
        namespace="default",
        body=job)
    print("Job updated. status='%s'" % str(api_response.status))


def delete_job(api_instance, job_name, namespace):
    try:
        api_response = api_instance.delete_namespaced_job(
            name=job_name,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=0))
        print("Job deleted. status='%s'" % str(api_response.status))
    except kubernetes.client.exceptions.ApiException as e:
        print('error deleting job, reason: {0}'.format(e.reason))


def delete_completed_jobs(batch_v1):
    completed = False
    jobs_list = []
    pending_job_list = []
    # Get a list of jobs (using pagination) in NAMESPACE. Retrieve a batch of 50 jobs at a time, until the _continue
    # flag returned by list_namespaced_job is false
    while not completed:
        limit = 50
        partial_job_list = batch_v1.list_namespaced_job(NAMESPACE, limit=limit, _continue=None)
        _continue = partial_job_list.metadata._continue
        jobs_list.extend(partial_job_list.items)
        if not _continue:
            completed = True
    # Run through the job list and delete successfully completed jobs. Any incomplete jobs are put on a pending job list
    for job in jobs_list:
        if job.status.completion_time is not None and job.status.succeeded == 1:
            print("deleting job {0}".format(job.metadata.name))
            delete_job(batch_v1, job_name=job.metadata.name, namespace=NAMESPACE)
        else:
            print("job {0} not complete, omitting deletion".format(job.metadata.name))
            pending_job_list.append(job)
    # If the number of pending jobs > 5, sleep for a bit an reattempt job deletion. The idea is to avoid having too
    # many incomplete jobs to avoid overwhelming the cluster.
    while len(pending_job_list) > 5:
        print("{0} pending jobs, sleeping for 2 seconds".format(len(pending_job_list)))
        time.sleep(1)
        print("reattempting job deletion")
        for job in pending_job_list:
            job_status = batch_v1.read_namespaced_job_status(job.metadata.name, NAMESPACE)
            if job_status.status.completion_time is not None and job_status.status.succeeded == 1:
                print("deleting job {0}".format(job.metadata.name))
                delete_job(batch_v1, job_name=job.metadata.name, namespace=NAMESPACE)
                pending_job_list.remove(job)


def main():
    # Load configuration k-v pairs from load_test_config.env. These k-v pairs include AWS creds, profile name,
    # SNS topic and SQS queue we'll be sending notifications, messages
    load_test_config = dotenv_values("load_test_config.env")
    for k, v in load_test_config.items():
        os.environ[k] = v

    aws_config = configparser.RawConfigParser()
    aws_config.read(os.getenv('AWS_CFG_PATH'))
    profile_name = os.getenv('AWS_PROFILE_NAME')
    config.load_kube_config()
    batch_v1 = client.BatchV1Api()

    # read aws user creds
    access_key_id = aws_config.get(profile_name, 'aws_access_key_id')
    aws_secret_access_key = aws_config.get(profile_name, 'aws_secret_access_key')

    session = boto3.Session(
        aws_access_key_id=access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    sqs = session.resource('sqs')
    sqs_queue_name = os.getenv("SQS_QUEUE_NAME")
    sqs_q = sqs.get_queue_by_name(QueueName=sqs_queue_name)
    sns_client = boto3.client('sns', region_name='us-east-1', aws_access_key_id=access_key_id,
                              aws_secret_access_key=aws_secret_access_key)
    sns_topic_arn = os.getenv('SNS_TOPIC_NAME')

    # Create a list of JSON formatted message strings where the author and id keys are sampled from a list of authors and
    # ids
    authors = ['Ankur', 'Brian', 'David']
    ids = [4, 5]
    author_list = []
    msgs = []
    num_msgs = 2400
    for i in range(0, num_msgs):
        msgs.append('{{"id":{0},"greeting":"{1}","message":"{2}", "author":"{3}"}}'
                    .format(ids[i % 2], "hello", "tbd", authors[i % 3]))
        author_list.append(authors[i % 3])

    rand_indices = random.sample(range(0, num_msgs), num_msgs)
    for i in rand_indices:
        print("sending message {0}".format(i))
        msg = msgs[i]
        # With SNS, the message will be included in the Message field of the body of the http payload, along with
        # lots of other info, such as Timestamp, TopicArn and several other fields
        response = sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=msg)

        # With SQS, the body itself is the message. The author is included in the message, but also sent
        # as a separate json object as part of MessageAttributes
        response = sqs_q.send_message(
            DelaySeconds=0,
            MessageAttributes={
                'Author': {
                    'DataType': 'String',
                    'StringValue': author_list[i],
                },
                'Timestamp': {
                    'DataType': 'String',
                    'StringValue': datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S.%f'),
                },
            },
            MessageBody=msg)
        # delete jobs and pods every 50 message, to avoid out-of-pod errors
        if i % 50 == 0:
            delete_completed_jobs(batch_v1)
        # random number from 0 to 1
        sleep_time = random.random()
        sleep_time = sleep_time*0.3
        # sleep for a random length of time between 0 and 0.3 seconds
        time.sleep(sleep_time)

    print('done')


if __name__ == '__main__':
    main()


