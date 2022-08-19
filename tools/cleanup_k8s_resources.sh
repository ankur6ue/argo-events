#!/bin/bash
NAMESPACE=$1

kubectl get jobs -n ${NAMESPACE} --no-headers=true | awk '/hello/{print $1}'| xargs  kubectl delete -n ${NAMESPACE} job
kubectl get pods -n ${NAMESPACE} --no-headers=true | awk '/hello/{print $1}'| xargs  kubectl delete -n ${NAMESPACE} pod
