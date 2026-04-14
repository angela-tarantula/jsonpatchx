FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:abb7fdbd9f6608a9cd0a4da05fd37558ac27caf58734334c3f557940cdcb9f46

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
