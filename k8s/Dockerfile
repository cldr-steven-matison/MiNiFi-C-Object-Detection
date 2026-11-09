# MiNiFi C++ 2.26.09 + minifi_tensor on Ubuntu 24.04 / python3.12, uid 1000 "minifi".
# Built to match an Ubuntu 24.04 edge box (a Jetson on JetPack 7 is the same OS and Python),
# so nothing proven in the pod needs more than the edge box has.
# Build context (k8s/build.sh assembles it): this Dockerfile, scripts/install.sh, scripts/run-agent.sh,
# the staged minifi.tar.gz and the model files. The vendor image is not used: it is x86_64 only
# and carries no extra extensions.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
# libpython3.12t64: the python lib loader needs the shared libpython3.12.so.1.0, which the
# python3 package does not install. Without it the agent aborts with "Failed to find libpython path".
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip libpython3.12t64 ffmpeg procps ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
# ubuntu:24.04 ships a uid-1000 user "ubuntu"; rename it
RUN usermod -l minifi -d /home/minifi -m ubuntu && groupmod -n minifi ubuntu
COPY install.sh run-agent.sh /opt/minifi-detect/
COPY minifi.tar.gz /tmp/minifi.tar.gz
COPY models/ /tmp/models/
RUN su minifi -c "bash /opt/minifi-detect/install.sh /tmp/minifi.tar.gz /home/minifi/minifi-cpp-2.26.09" \
    && install -o minifi -g minifi -m 644 /tmp/models/* /home/minifi/minifi-cpp-2.26.09/models/ \
    && rm -rf /tmp/minifi.tar.gz /tmp/models
USER minifi
WORKDIR /home/minifi
ENV MINIFI_HOME=/home/minifi/minifi-cpp-2.26.09
CMD ["bash", "/opt/minifi-detect/run-agent.sh", "/conf", "/home/minifi/minifi-cpp-2.26.09"]
