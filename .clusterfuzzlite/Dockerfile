FROM gcr.io/oss-fuzz-base/base-builder-python

# ClusterFuzzLite's `compile` entrypoint executes `/src/build.sh`.
# Keep repository sources under `$SRC/jsonpatchx`, but expose the expected
# top-level build script path as well.
WORKDIR $SRC
COPY . $SRC/jsonpatchx
COPY .clusterfuzzlite/build.sh $SRC/build.sh
RUN chmod +x $SRC/build.sh
