(Argo Events)[https://argoproj.github.io/argo-events/] is an event-driven workflow automation framework for Kubernetes which helps you trigger K8s objects, Argo Workflows, Serverless workloads, etc. on events from a variety of sources like webhooks, S3, schedules, messaging queues, gcp pubsub, sns, sqs, etc.
This project demonstrates the following features:
- Installing argo events on a Kubernetes cluster set up by kops on AWS
- Setting up AWS SQS and SNS event sources, with event filtering
- Setting up event sensors for SQS and SNS events with filtering
- Setting up separate triggers for each event type. SNS events trigger an http request to a service, while SQS events launch a kubernetes job. The event payload is sent in the body of the HTTP request and passed as command line parameters to the k8s job container 
- The http service and kubernetes job parses the event payload and records the event info in a mysql database
- Setting up RBAC, such that the Kubernetes job is created in a different namespace from where the argo events pods are running
- Exposing argo events custom metrics in a prometheus dashboard

The information recorded in the database includes the time when the event (SQS message or SNS notification) is sent and when the corresponding database entry is created. This information can be used to analyze the total delay introduced in the event processing pipeline

Our test script  Create a list of JSON formatted message strings where the author and id keys are sampled from a list of authors and
ids
3. Run through this list and send each message to the SNS topic and SQS queue. The duration between each message
is randomly sampled between 0 - 3000ms. 
4. Every 50 messages, use the kubernetes-python API to delete completed jobs (created by the SQS trigger). This is done
to avoid having too many completed jobs on the cluster, which can result in out-of-pods error. 
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