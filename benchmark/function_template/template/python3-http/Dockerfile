FROM --platform=${TARGETPLATFORM:-linux/amd64} ghcr.io/openfaas/of-watchdog:0.9.10 as watchdog
# FROM --platform=${TARGETPLATFORM:-linux/amd64} python:3.7-slim-buster as build

FROM --platform=${TARGETPLATFORM:-linux/amd64} nvcr.io/nvidia/pytorch:22.12-py3

COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog

ARG ADDITIONAL_PACKAGE
# Alternatively use ADD https:// (which will not be cached by Docker builder)

RUN apt-get -qy update \
    && apt-get -qy install ${ADDITIONAL_PACKAGE} \
    && rm -rf /var/lib/apt/lists/*

# Add non root user
RUN addgroup --system app && adduser app --system --ingroup app
RUN chown app /home/app

USER app
ENV PATH=$PATH:/home/app/.local/bin
WORKDIR /home/app/
RUN mkdir -p function
RUN touch ./function/__init__.py
COPY --chown=app:app requirements.txt   .
RUN pip install --user -r requirements.txt --proxy=http://172.20.110.31:10081

COPY --chown=app:app function/requirements.txt	./function/
RUN pip install  --user -r ./function/requirements.txt --proxy=http://172.20.110.31:10081

COPY --chown=app:app function      function
COPY --chown=app:app function/index.py      .


USER app
WORKDIR /home/app/

# Set up of-watchdog for HTTP mode
ENV fprocess="python index.py"
ENV cgi_headers="true"
ENV mode="http"
ENV upstream_url="http://127.0.0.1:5000"

HEALTHCHECK --interval=5s CMD [ -e /tmp/.lock ] || exit 1

CMD ["fwatchdog"]
