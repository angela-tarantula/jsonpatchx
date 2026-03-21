#!/bin/bash -eu

REPO_DIR="${SRC:-/src}/jsonpatchx"
cd "$REPO_DIR"

python --version
python -m pip install .

compile_python_fuzzer fuzzers/jsonpatchx_fuzzer.py \
  --output_name jsonpatchx_fuzzer
compile_python_fuzzer fuzzers/jsonpatchx_custom_backend_fuzzer.py \
  --output_name jsonpatchx_custom_backend_fuzzer

cp fuzzers/jsonpatchx_fuzzer.dict "$OUT/jsonpatchx_fuzzer.dict"
cp fuzzers/jsonpatchx_custom_backend_fuzzer.dict \
  "$OUT/jsonpatchx_custom_backend_fuzzer.dict"

zip -j "$OUT/jsonpatchx_fuzzer_seed_corpus.zip" \
  fuzzers/corpus/jsonpatchx_fuzzer/*
zip -j "$OUT/jsonpatchx_custom_backend_fuzzer_seed_corpus.zip" \
  fuzzers/corpus/jsonpatchx_custom_backend_fuzzer/*
