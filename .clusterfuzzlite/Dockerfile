FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:e0e18dea5d2e4107a4f5d04652e6c278fbea32dc6d6861ee8de29402d0916746

# Pin dependencies
COPY .clusterfuzzlite/requirements-bootstrap.txt /tmp/requirements-bootstrap.txt

# Default Python 3.11 is no good for JsonPatchX which is Py3.12+
RUN python3 -m pip install --disable-pip-version-check --require-hashes \
      --only-binary=:all: -r /tmp/requirements-bootstrap.txt && \
    uv python install 3.13 && \
    PYTHON_BIN="$(uv python find 3.13)" && \
    "$PYTHON_BIN" -m venv /opt/python313

ENV PATH="/opt/python313/bin:${PATH}"

COPY . $SRC/jsonpatchx
WORKDIR $SRC/jsonpatchx

# Install dependencies with Py3.13
RUN . /opt/python313/bin/activate && \
    uv sync --frozen --python /opt/python313/bin/python --no-default-groups --group fuzz --active

COPY .clusterfuzzlite/build.sh $SRC/
