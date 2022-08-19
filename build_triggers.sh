# build trigger images and push to docker hub
cd ./sns-trigger-app
./build_push.sh
cd ../sqs-trigger-app
./build_push.sh
