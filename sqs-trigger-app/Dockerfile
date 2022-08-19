FROM python:3.8.10 as base_image
RUN apt-get update && \
      apt-get -y install sudo
ENV BASE_DIR=/app
RUN sudo mkdir -p $BASE_DIR
WORKDIR $BASE_DIR
COPY app.py $BASE_DIR/
COPY requirements.txt $BASE_DIR/
RUN pip install -r requirements.txt
# RUN sudo apt-get update
ENTRYPOINT [ "python", "app.py", "--msg"]
CMD [ "dummy" ]
# CMD ./run.sh
# To run shell by overriding entrypoint: docker run --name echo_app --rm -it --entrypoint /bin/bash echo_app
