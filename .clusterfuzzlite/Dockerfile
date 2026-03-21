FROM gcr.io/oss-fuzz-base/base-builder-python

RUN python3 -m pip install --upgrade uv && \
    uv python install 3.13 && \
    PYTHON_BIN="$(uv python find 3.13)" && \
    "$PYTHON_BIN" -m venv /opt/python313

ENV PATH="/opt/python313/bin:${PATH}"

WORKDIR $SRC
COPY . $SRC/jsonpatchx
COPY .clusterfuzzlite/build.sh $SRC/build.sh
RUN chmod +x $SRC/build.sh
