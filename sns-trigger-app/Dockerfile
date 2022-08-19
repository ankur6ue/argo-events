FROM python:3.8.10 as base_image
RUN apt-get update && \
      apt-get -y install sudo
ENV BASE_DIR=/app
RUN pip install "fastapi[all]"
RUN sudo mkdir -p $BASE_DIR
WORKDIR $BASE_DIR
COPY app.py $BASE_DIR/
COPY requirements.txt $BASE_DIR/
RUN pip install -r requirements.txt
# RUN sudo apt-get update
EXPOSE 8000
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]

# docker run --name http-server -p 8000:8000 ankur6ue/sns_trigger_app

