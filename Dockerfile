FROM python:3.13.3-bookworm

WORKDIR /

RUN mkdir /compiler2
RUN mkdir /garbage_collector
RUN mkdir /app

COPY requirements.txt .

RUN apt update
RUN apt install -y llvm-15 clang-15
RUN python3 -m pip install -r requirements.txt

COPY ./compiler2/* /compiler2
COPY garbage_collector/ps_re.bc garbage_collector

WORKDIR /app
ENV LLVM_VERSION="15"

ENTRYPOINT ["python3", "/compiler2/main.py"]
CMD ["--help"]