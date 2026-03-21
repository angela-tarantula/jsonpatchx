#!/bin/bash -eu

# CFLite invokes this script as /src/build.sh; switch to repo root first
REPO_DIR="${SRC:-/src}/jsonpatchx"
cd "$REPO_DIR"

python -m pip install --upgrade uv
uv python install 3.13
PYTHON_BIN="$(uv python find 3.13)"
export PATH="$(dirname "$PYTHON_BIN"):$PATH"

python --version
python -m pip install --upgrade pip
python -m pip install atheris
python -m pip install .

# Compile fuzz targets into libFuzzer-compatible entrypoints
compile_python_fuzzer fuzzers/jsonpatchx_fuzzer.py \
  --output_name jsonpatchx_fuzzer
compile_python_fuzzer fuzzers/jsonpatchx_custom_backend_fuzzer.py \
  --output_name jsonpatchx_custom_backend_fuzzer

# Ship dictionaries for token-aware mutations
cp fuzzers/jsonpatchx_fuzzer.dict "$OUT/jsonpatchx_fuzzer.dict"
cp fuzzers/jsonpatchx_custom_backend_fuzzer.dict \
  "$OUT/jsonpatchx_custom_backend_fuzzer.dict"

# Ship seed corpora for both targets
zip -j "$OUT/jsonpatchx_fuzzer_seed_corpus.zip" \
  fuzzers/corpus/jsonpatchx_fuzzer/*
zip -j "$OUT/jsonpatchx_custom_backend_fuzzer_seed_corpus.zip" \
  fuzzers/corpus/jsonpatchx_custom_backend_fuzzer/*
