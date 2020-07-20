FROM debian:buster-slim

WORKDIR /home

RUN apt update
RUN apt install -y git python3 python3-future libtool autoconf pkg-config g++ systemd make
RUN git clone https://github.com/intel/mavlink-router

WORKDIR /home/mavlink-router
RUN git submodule update --init --recursive
RUN ./autogen.sh && ./configure --disable-dependency-tracking
RUN make
RUN make install
