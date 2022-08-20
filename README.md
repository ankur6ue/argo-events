(Argo Events)[https://argoproj.github.io/argo-events/] is an event-driven workflow automation framework for Kubernetes which helps you trigger K8s objects, Argo Workflows, Serverless workloads, etc. on events from a variety of sources like webhooks, S3, schedules, messaging queues, gcp pubsub, sns, sqs, etc.
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
![](system_architecture)

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
Log into AWS console and create a SQS queue and a SNS topic with default settings. We'll use the AWS credentials associated with the user profile used to create these resources to communicate with them. 


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