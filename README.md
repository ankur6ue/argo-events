[Argo Events](https://argoproj.github.io/argo-events/) is an event-driven workflow automation framework for Kubernetes which helps you trigger K8s objects, Argo Workflows, Serverless workloads, etc. on events from a variety of sources like webhooks, S3, schedules, messaging queues, gcp pubsub, sns, sqs, etc.
This project demonstrates the following features:
- Installing argo events on a Kubernetes cluster set up by kops on AWS
- Setting up AWS SQS and SNS event sources, with event filtering
- Setting up event sensors for SQS and SNS events with filtering
- Setting up separate triggers for each event type. SNS event trigger POSTs a http request to a service, while the SQS event trigger launches a kubernetes job. The event payload is sent in the body of the HTTP request and passed as command line parameters to the k8s job container 
- The http service and kubernetes job parses the event payload and records the event info in a mysql database
- Setting up RBAC, such that the Kubernetes job is created in a different namespace from where the argo events pods are running
- Exposing argo events custom metrics in a prometheus dashboard

The information recorded in the database includes the time when the event (SQS message or SNS notification) is sent and when the corresponding database entry is created. This information can be used to analyze the total delay introduced in the event processing pipeline

## System Architecture
The overall system architecture is shown below with some system components marked with numerals. I'll be using the numerals to refer to those components in the description henceforth. 
![](images/system_architecture)

Our test script (load_test.py (#1)) creates a list of 2400 JSON formatted message strings with the following format:
```json
{
  "id": 4, # selected from [4, 5]
  "greeting": "hello",
  "message": "hello world",
  "author": "Ankur" # selected from ["Ankur", "David", "Brian"]
}

```
Here the value of the `author` key is sampled from a list of authors ("Ankur", "Brian", "David") and the value of the `id` key is sampled from (4, 5). We then generate a list of random indices from this list and send each randomly selected message to the SQS queue and SNS topic. The duration between each message is randomly sampled between 0 - 3000ms. The SQS event source (#2) filters for messages with id == 4, while no filtering is applied on the SNS event source (#2). The SQS event sensor (#3) filters for author == 'Ankur', while the SNS event sensor (#3) filters for author == 'David'. Thus a total of 1200 messages (2400*[1/2*1/3] + 2400*1/3) pass the source and sensor filtering stages. The SQS event sensor is configured to launch a kubernetes Job (#4), that connects to a mysql database (#5) and creates an event record with information about the event payload and the event and record creation  time. The SNS event sensor is configured to make a POST request to a HTTP server (#4) that also connects to the mysql database (#5) and creates an event record with information about the event payload and the event and record creation  time.

Every 50 messages, we use the kubernetes-python API to delete completed jobs (created by the SQS trigger). The purpose is to avoid having too many completed jobs on the cluster, which can result in out-of-pods error. 

After the test script has finished running, we connect to mysql db and dump the data to a csv file. I've included a python [script](/tools/analysis.py) that reads the csv file into a dataframe, splits by eventtype (sns or sqs), and computes the difference between when the event was sent and when the corresponding database entry was created. This difference is the total delay in the event processing pipeline. The min and max delay is printed and a histogram of the delay is plotted for each event type. Intuition suggests the delay should be higher for SQS event type, because a k8s job is triggered for each message, and as shown in the results section below, this is indeed true.

### Prerequisites
This project is based on the following set up:

- A Kubernetes cluster on AWS. I used [kops](https://kops.sigs.k8s.io/getting_started/install/) to set up a cluster consisting of a 1 master and 2 worker nodes (t2.medium EC2 instances). I won't go into the cluster set up in detail in this post. 
- Default argo events installation from [here](https://argoproj.github.io/argo-events/installation/). After following these instructions, you should see the eventbus and controller-manager pods running in the argo-events namespace

### Setup
#### SQS and SNS
Log into AWS console and create a SQS queue and a SNS topic with default settings. In the next step, we'll use the AWS credentials associated with the user profile used to create these resources (or a profile with the proper access to these resources) to create a Kubernetes secret 

#### Creating a Kubernetes Secret containing your user credentials
Follow instructions [here](https://argoproj.github.io/argo-events/eventsources/setup/aws-sqs/) to create a kubernetes Secret containing your AWS account access and secret key. You'll need to base64 encode the keys, which can be done using a command line tool, or using this [web tool](https://www.base64encode.org/)
```commandline

```
#### Set up SQS and SNS event source
The SQS an SNS event source custom resource are defined in k8s/aws-sns-source.yaml and k8s/aws-sqs-source.yaml. Add your SQS queue name (not the full ARN) to the queue field in the SQS source config, and the SNS topic ARN to the topicARN field. Run kubectl apply as shown below
```commandline
kubectl apply -f k8s/aws-sns-source.yaml -n argo-events
kubectl apply -f k8s/aws-sqs-source.yaml -n argo-events
```

Now run 
```commandline
kubectl get pods -n argo-events
```
You'll see pods for the SQS and SNS event source. If you run `kubectl get svc -n argo-events`, you'll see the SNS pod has been exposed as a service. The name for the service is in <event-source-name>-eventsource-svc format. 
This is done because the SNS source must expose an internet facing endpoint that can be called by SNS. To expose the service to the internet, run 
```commandline
kubectl apply -f k8s/ingress.yaml -n argo-events
``` 
This will create an ingress that will expose your service to the internet on `your_cluster_elb_address/aws-sns-source`. The other section in the ingress config exposes a mysql service to the internet, which we haven't created yet. 

You can get your ELB address by running `kubectl get ingress -n argo-events`
Now, replace the `url` field in `aws-sns-source.yaml` with `your_cluster_elb_address/aws-sns-source` and apply the change. During subscription, The SNS event source provides the address of the internet facing endpoint to AWS SNS which is used by SNS to verify the subscription. Now if you go to the AWS SNS console, you should see a verified subscription. The SQS event source polls for new messages on the queue, and is not associated with a service. 

Note that the SQS event applies a source filter which only selects messages where body.id == 4. The `jsonBody: true` statement instructs the event source to interpret the body of message as JSON. 

Now try sending a JSON formatted SQS message/SNS notification using the AWS console and check the logs for the event source pod using `kubectl logs <pod_name> -n argo-events`. You should see some info about the message you sent using the console in the logs if the setup is working correctly. 

### Building docker images for event triggers
Next, we'll build the docker images used in the event triggers triggered by the SNS and SQS event sensors. The code for the event triggers are in the `sns-trigger-app` and `sqs-trigger-app` folders respectively. The sns trigger runs a kubernetes job that connects to a mysql database and adds a record in the database with the event info. The sqs trigger POSTs the event info to a web service with a single endpoint. The endpoint handler parses the body of the request and adds a record in the mysql database. The event creation time and database record creation time are also recorded, which are used to measure the lag in the event processing pipeline, as mentioned above. The implementation is fairly straightforward. Note that the event creation and record creation time must be in the same time zone. Because I can't be sure of the time zone of the EC2 instance where the triggers run, I convert the record creation time to eastern time zone, where my test script is running. 

To build the trigger docker images, you can use build_trigger.sh, which calls the build_push.sh scripts in sns-trigger-app and sqs-trigger-app folders. Before running the script, you should change dockerhub userid in the image name to your user id.

### Running mysql pod and service
The events that pass source and sensor filtering are recorded in a mysql database. To set it up, do the following
- Create the persistent volume and claim needed by the database:
```commandline
kubectl apply -f k8s/mysql-pv.yaml
```
- Create the mysql deployment and service
```commandline
kubectl apply -f mysql.yaml
```
To check if the db set up is working, you can run a mysql client and connect to the database
```commandline
kubectl run -it --rm --image=mysql:5.6 -n argo-events --restart=Never mysql-client -- mysql -h mysql -ppassword -uroot
```
You can also use port forwarding to access the mysql pod directly from your workstation. This lets you use an IDE such as Pycharm to interact with the database, which is a much easier user experience. 
```commandline
 kubectl port-forward -n argo-events <my-sql-podname> 27018:3306
```
If you are using Pycharm, use the settings shown in this screenshot to connect with the database:
![](images/pycharm_db_conn_screenshot)

Using one of the sql clients, connect to the database server and create a database and table with the following schema:
```sql
CREATE DATABASE IF NOT EXISTS argo_event_record_db;
USE argo_event_record_db;
DROP TABLE argo_event_record;
CREATE TABLE IF NOT EXISTS argo_event_record(
  Id      INT     NOT NULL   AUTO_INCREMENT    PRIMARY KEY,
  PayloadId INT,
  EventType TEXT,
  CustomMessage TEXT,
  Author VARCHAR(255),
  EventTimestamp Timestamp(3), # the (3) ensures we are capturing milisecond level info
  CreatedAtTimestamp Timestamp(3)
);
```
### RBAC for the Kubernetes job created by SQS event sensor
One of the issues we want to verify in this project is the ability to create a Kubernetes resource in a different namespace from where the argo-events pods are running. The obvious choice for this resource is the job triggered by SQS events. To do so, we create a namespace called `argo-events-test`
```sql
kubectl create namespace argo-events-test
```
Then you can run `kubectl apply -f k8s\create-deploy-pod-rbac.yaml`. This creates a new service account (change the name as appropriate), a role that enables CRUD operations on pods and jobs in the `argo-events-test` namespace, and a rolebinding that binds the new service account to this role, but itself lives in the `argo-events-test` namespace. This configuration is 'least privilege' because it only gives our new service account a specific set of permissions in a specific namespace, and no more. 
Read [this](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) if you are unfamiliar with RBAC on kubernetes, 
### Setting up SQS and SNS event sensor
Next, we'll set up our event sensor. I've included both the SQS and SNS sensor configurations in the same yaml file (aws-sensor.yaml) to show that you can include multiple sensors in the same yaml file. 

There are two parts to configuring a sensor. The first part is called event dependency and is related to specifying the event source the sensor responds to. You can also also specify event transformations (using JQ or Lua) and filtering in this section. The event transformation is applied before the filtering stage. 
The second part is called event trigger and specifies the action that should take place in response to an event that passes the filtering stage. These triggers can include triggering an argo workflow, AWS lambda, HTTP request, Kubernetes object and several others. See [this](https://argoproj.github.io/argo-events/sensors/transform/) for a complete list. 

For the SQS sensor, the transformation step consists of modifying the message field in the event body and the filtering step filters on the author field of the SQS MessageAttributes (see load_test.py for the SQS message format). Note that we set jsonBody field Events that pass the filtering stage trigger a Kubernetes job in the argo-events-test namespace. The message info is passed as an argument to the container in the job spec. The kubernetes job parses the message info and adds a record in a table in the mysql database. 

For the SNS sensor, the transformation step is more complex. Unlike the SQS message that includes the message creation timestamp in the MessageAttributes field, the SNS message doesn't contain the message creation timestamp. Instead, we rely on the timestamp inserted by AWS SNS in the message body and copy this timestamp to the Message.Timestamp field. This also demonstrates that the event transformation mechanism can be used to insert a new field in the message body. 
The filtering step is similar to the SQS sensor. We filter on the author field of the message body. 



It listens to events on the eventbus and acts as an event dependency manager to resolve and execute the triggers.







### Prometheus setup
#### Expose prometheus deployment using an ingress or nodeport service
#### Add job config
#### Test exposed metrics
```
kubectl run mycurlpod -n argo-events --image=curlimages/curl -i --tty -- sh
```

```angular2
curl -G 100.121.101.67:7777/metrics
```